#include "LabInt.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "platform.h"

// ── Line ─────────────────────────────────────────────────────────────────────────────────────────

void LabInt::Line::start(LabInt* owner, const char* head) {
  owner_ = owner;
  len_ = 0;
  overflow_ = false;
  buf_[0] = 0;
  append(head);
}

void LabInt::Line::append(const char* text) {
  size_t n = strlen(text);
  if (len_ + n >= sizeof(buf_)) {
    overflow_ = true;
    return;
  }
  memcpy(buf_ + len_, text, n + 1);
  len_ += n;
}

static bool needsQuotes(const char* v) {
  if (!*v) return true;
  for (; *v; ++v)
    if (*v == ' ' || *v == '\t' || *v == '"' || *v == '\\') return true;
  return false;
}

LabInt::Line& LabInt::Line::kv(const char* key, const char* value) {
  append(" ");
  append(key);
  append("=");
  if (!needsQuotes(value)) {
    append(value);
    return *this;
  }
  append("\"");
  char one[2] = {0, 0};
  for (const char* p = value; *p; ++p) {
    if (*p == '"' || *p == '\\') append("\\");
    one[0] = *p;
    append(one);
  }
  append("\"");
  return *this;
}

LabInt::Line& LabInt::Line::kv(const char* key, long value) {
  char num[16];
  snprintf(num, sizeof(num), "%ld", value);
  return kv(key, (const char*)num);
}

LabInt::Line& LabInt::Line::kv(const char* key, unsigned long value) {
  char num[16];
  snprintf(num, sizeof(num), "%lu", value);
  return kv(key, (const char*)num);
}

LabInt::Line& LabInt::Line::kv(const char* key, double value, uint8_t decimals) {
  char num[24];
  // dtostrf-free formatting that works on every core: integer part and fraction, always '.'
  bool negative = value < 0;
  if (negative) value = -value;
  unsigned long scale = 1;
  for (uint8_t i = 0; i < decimals; ++i) scale *= 10;
  unsigned long whole = (unsigned long)value;
  unsigned long frac = (unsigned long)((value - whole) * scale + 0.5);
  if (frac >= scale) { whole += 1; frac -= scale; }
  if (decimals)
    snprintf(num, sizeof(num), "%s%lu.%0*lu", negative ? "-" : "", whole, (int)decimals, frac);
  else
    snprintf(num, sizeof(num), "%s%lu", negative ? "-" : "", whole);
  return kv(key, (const char*)num);
}

void LabInt::Line::send() {
  if (!owner_) return;
  if (overflow_) {
    owner_->write("ERR 6 reply too long");
  } else {
    owner_->write(buf_);
  }
  owner_ = nullptr;
}

// ── Request ──────────────────────────────────────────────────────────────────────────────────────

const char* LabInt::Request::field(const char* key) const {
  size_t n = strlen(key);
  for (uint8_t i = 0; i < argc_; ++i)
    if (strncmp(argv_[i], key, n) == 0 && argv_[i][n] == '=') return argv_[i] + n + 1;
  return nullptr;
}

long LabInt::Request::intArg(uint8_t i, long def, long min, long max) {
  if (answered_) return def;
  const char* a = arg(i);
  if (!a) return def;
  char* end = nullptr;
  long v = strtol(a, &end, 10);
  if (end == a || *end) {
    fail(ERR_ARGUMENT, "argument must be an integer");
    return def;
  }
  if (v < min || v > max) {
    char msg[48];
    snprintf(msg, sizeof(msg), "out of range %ld..%ld", min, max);
    fail(ERR_RANGE, msg);
    return def;
  }
  return v;
}

double LabInt::Request::floatArg(uint8_t i, double def, double min, double max) {
  if (answered_) return def;
  const char* a = arg(i);
  if (!a) return def;
  char* end = nullptr;
  double v = strtod(a, &end);
  if (end == a || *end) {
    fail(ERR_ARGUMENT, "argument must be a number");
    return def;
  }
  if (v < min || v > max) {
    fail(ERR_RANGE, "out of range");
    return def;
  }
  return v;
}

const char* LabInt::Request::strArg(uint8_t i, const char* def) {
  const char* a = arg(i);
  return a ? a : def;
}

LabInt::Line& LabInt::Request::ok() {
  answered_ = true;
  ok_ = true;
  owner_->out_.start(owner_, "OK");
  if (fn_) owner_->out_.kv("fn", fn_->name_);
  return owner_->out_;
}

void LabInt::Request::busy() {
  answered_ = true;
  ok_ = true;
  if (fn_) {
    strncpy(fn_->busyVerb_, verb_, sizeof(fn_->busyVerb_) - 1);
    fn_->busyVerb_[sizeof(fn_->busyVerb_) - 1] = 0;
  }
  owner_->out_.start(owner_, "BUSY");
  if (fn_) owner_->out_.kv("fn", fn_->name_);
  owner_->out_.send();
}

void LabInt::Request::fail(uint8_t code, const char* message) {
  if (answered_) return;
  answered_ = true;
  ok_ = false;
  char head[8];
  snprintf(head, sizeof(head), "ERR %u", code);
  owner_->out_.start(owner_, head);
  owner_->out_.append(" ");
  owner_->out_.append(message);
  owner_->out_.send();
}

// ── Function ─────────────────────────────────────────────────────────────────────────────────────

LabInt::Function& LabInt::Function::on(const char* verb, Handler handler) {
  if (ncommands_ < LABINT_MAX_COMMANDS) commands_[ncommands_++] = {verb, handler};
  return *this;
}

LabInt::Function& LabInt::Function::hw(const char* key, const char* value) {
  for (uint8_t i = 0; i < nhw_; ++i)
    if (strcmp(hwKeys_[i], key) == 0) {
      hwValues_[i] = value;
      return *this;
    }
  if (nhw_ < LABINT_MAX_HW) {
    hwKeys_[nhw_] = key;
    hwValues_[nhw_++] = value;
  }
  return *this;
}

LabInt::Line& LabInt::Function::done() {
  Line& line = owner_->event("DONE", this);
  line.kv("cmd", (const char*)busyVerb_);
  busyVerb_[0] = 0;
  return line;
}

void LabInt::Function::fault(uint8_t code, const char* message) {
  Line& line = owner_->event("FAULT", this);
  if (busyVerb_[0]) line.kv("cmd", (const char*)busyVerb_);
  line.kv("code", (long)code).kv("msg", message).send();
  busyVerb_[0] = 0;
}

// ── LabInt ───────────────────────────────────────────────────────────────────────────────────────

LabInt::LabInt(const char* firmwareVersion, const char* boardType)
    : firmware_(firmwareVersion), boardType_(boardType ? boardType : labint_platform::boardType()) {}

LabInt::Function& LabInt::function(const char* name) {
  for (uint8_t i = 0; i < nfunctions_; ++i)
    if (strcmp(functions_[i].name_, name) == 0) return functions_[i];
  if (nfunctions_ >= LABINT_MAX_FUNCTIONS) return functions_[nfunctions_ - 1];
  Function& f = functions_[nfunctions_++];
  f.owner_ = this;
  f.name_ = name;
  return f;
}

void LabInt::begin(Stream& link) {
  link_ = &link;
  loadIdentity();
  event("BOOT").kv("proto", (long)LABINT_PROTOCOL).send();
}

void LabInt::poll() {
  if (!link_) return;
  while (link_->available() > 0) {
    int c = link_->read();
    if (c < 0) break;
    if (c == '\r') continue;
    if (c == '\n') {
      if (inOverflow_) {
        write("ERR 2 line too long");
      } else if (inLen_ > 0) {
        in_[inLen_] = 0;
        handleLine(in_);
      }
      inLen_ = 0;
      inOverflow_ = false;
      continue;
    }
    if (inLen_ + 1 < sizeof(in_)) {
      in_[inLen_++] = (char)c;
    } else {
      inOverflow_ = true;
    }
  }
}

LabInt::Line& LabInt::event(const char* name, Function* fn) {
  char head[20];
  snprintf(head, sizeof(head), "EVT %s", name);
  out_.start(this, head);
  if (fn) out_.kv("fn", fn->name_);
  return out_;
}

void LabInt::debug(const char* text) {
  if (!link_) return;
  link_->print("# ");
  link_->print(text);
  link_->print("\n");
}

void LabInt::write(const char* text) {
  if (!link_) return;
  link_->print(text);
  link_->print("\n");
}

// Split in place on spaces; double quotes group, \" and \\ escape inside quotes.
static uint8_t tokenize(char* line, const char** argv, uint8_t max) {
  uint8_t n = 0;
  char* r = line;
  while (*r) {
    while (*r == ' ' || *r == '\t') ++r;
    if (!*r) break;
    char* w = r;
    if (n < max) argv[n] = w;
    bool quoted = false;
    while (*r && (quoted || (*r != ' ' && *r != '\t'))) {
      if (*r == '"') {
        quoted = !quoted;
        ++r;
      } else if (quoted && *r == '\\' && r[1]) {
        *w++ = r[1];
        r += 2;
      } else {
        *w++ = *r++;
      }
    }
    if (*r) ++r;
    *w = 0;
    ++n;
  }
  return n < max ? n : max;
}

void LabInt::handleLine(char* line) {
  const char* argv[LABINT_MAX_ARGS + 1];
  uint8_t n = tokenize(line, argv, LABINT_MAX_ARGS + 1);
  if (n == 0) return;

  Request rq;
  rq.owner_ = this;
  // "function:VERB" or "VERB"
  char* head = (char*)argv[0];
  char* colon = strchr(head, ':');
  if (colon) {
    *colon = 0;
    rq.verb_ = colon + 1;
    for (uint8_t i = 0; i < nfunctions_; ++i)
      if (strcmp(functions_[i].name_, head) == 0) rq.fn_ = &functions_[i];
    if (!rq.fn_) {
      rq.fail(ERR_UNKNOWN, "unknown function");
      return;
    }
  } else {
    rq.verb_ = head;
  }
  rq.argc_ = n - 1;
  for (uint8_t i = 1; i < n; ++i) rq.argv_[i - 1] = argv[i];

  if (!rq.fn_) {
    if (boardCommand(rq)) return;
    if (nfunctions_ == 1) rq.fn_ = &functions_[0];  // single-function board: prefix optional
    else {
      rq.fail(ERR_UNKNOWN, "unknown command");
      return;
    }
  }

  Function* fn = rq.fn_;
  if (strcmp(rq.verb_, "STOP") == 0) {
    rq.ok().send();
    stopAll(fn);
    return;
  }
  if (strcmp(rq.verb_, "HW?") == 0) {
    Line& line = rq.ok();
    for (uint8_t i = 0; i < fn->nhw_; ++i) line.kv(fn->hwKeys_[i], fn->hwValues_[i]);
    line.send();
    return;
  }
  if (fn->busy()) {
    rq.fail(ERR_BUSY, "busy");
    return;
  }
  for (uint8_t i = 0; i < fn->ncommands_; ++i) {
    if (strcmp(fn->commands_[i].verb, rq.verb_) == 0) {
      fn->commands_[i].handler(rq);
      if (!rq.answered_) rq.ok().send();  // a handler that says nothing succeeded
      return;
    }
  }
  rq.fail(ERR_UNKNOWN, "unknown command");
}

bool LabInt::boardCommand(Request& rq) {
  const char* v = rq.verb_;
  if (strcmp(v, "ID?") == 0) {
    char functions[64] = {0};
    for (uint8_t i = 0; i < nfunctions_; ++i) {
      if (i) strncat(functions, ",", sizeof(functions) - strlen(functions) - 1);
      strncat(functions, functions_[i].name_, sizeof(functions) - strlen(functions) - 1);
    }
    rq.ok().kv("proto", (long)LABINT_PROTOCOL).kv("board", boardType_).kv("fw", firmware_)
        .kv("serial", (const char*)serial_).kv("name", (const char*)name_)
        .kv("functions", (const char*)functions).kv("links", "usb").send();
    return true;
  }
  if (strcmp(v, "PING") == 0) {
    rq.ok().send();
    return true;
  }
  if (strcmp(v, "STATUS?") == 0) {
    Line& line = rq.ok();
    for (uint8_t i = 0; i < nfunctions_; ++i) line.kv(functions_[i].name_, functions_[i].busy() ? "busy" : "idle");
    line.send();
    return true;
  }
  if (strcmp(v, "CMDS?") == 0) {
    Line& line = rq.ok();
    for (uint8_t i = 0; i < nfunctions_; ++i) {
      char list[LABINT_LINE];
      strcpy(list, "HW?,STOP");
      for (uint8_t c = 0; c < functions_[i].ncommands_; ++c) {
        strncat(list, ",", sizeof(list) - strlen(list) - 1);
        strncat(list, functions_[i].commands_[c].verb, sizeof(list) - strlen(list) - 1);
      }
      line.kv(functions_[i].name_, (const char*)list);
    }
    line.send();
    return true;
  }
  if (strcmp(v, "STOP") == 0) {
    rq.ok().send();
    stopAll(nullptr);
    return true;
  }
  if (strcmp(v, "RESET") == 0) {
    stopAll(nullptr);
    for (uint8_t i = 0; i < nfunctions_; ++i)
      if (functions_[i].reset_) functions_[i].reset_();
    rq.ok().send();
    return true;
  }
  if (strcmp(v, "NAME") == 0) {
    const char* name = rq.arg(0);
    if (!name || !*name) {
      rq.fail(ERR_ARGUMENT, "name required");
      return true;
    }
    strncpy(name_, name, sizeof(name_) - 1);
    name_[sizeof(name_) - 1] = 0;
    labint_platform::saveName(name_);
    rq.ok().send();
    return true;
  }
  if (strcmp(v, "AUTH") == 0) {  // USB needs no token
    rq.ok().send();
    return true;
  }
  if (strcmp(v, "NET?") == 0 || strcmp(v, "WIFI") == 0 || strcmp(v, "TOKEN?") == 0) {
    rq.fail(ERR_UNSUPPORTED, "no Wi-Fi on this board");
    return true;
  }
  return false;
}

void LabInt::stopAll(Function* only) {
  for (uint8_t i = 0; i < nfunctions_; ++i) {
    Function& f = functions_[i];
    if ((only && &f != only) || !f.busy()) continue;
    Line& line = event("STOPPED", &f);
    line.kv("cmd", (const char*)f.busyVerb_);
    f.busyVerb_[0] = 0;
    if (f.stop_) f.stop_(line);
    line.send();
  }
}

void LabInt::loadIdentity() {
  labint_platform::serialNumber(serial_, sizeof(serial_));
  labint_platform::loadName(name_, sizeof(name_));
  if (!name_[0]) snprintf(name_, sizeof(name_), "LabInt-%.4s", serial_);
}

uint8_t LabInt::setting(uint8_t slot, uint8_t def) const { return labint_platform::loadSetting(slot, def); }

void LabInt::setSetting(uint8_t slot, uint8_t value) { labint_platform::saveSetting(slot, value); }
