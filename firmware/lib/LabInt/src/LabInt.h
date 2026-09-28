// LabInt: the board side of the LabInt wire protocol, version 1 (firmware/PROTOCOL.md).
//
//   LabInt board("2.0.0");
//   LabInt::Function& photo = board.function("photometer");
//   void cmdRead(LabInt::Request& rq) { ... rq.ok().kv("bb", 5691).send(); }
//   void setup() { photo.on("READ", cmdRead); board.begin(Serial); }
//   void loop()  { board.poll(); }            // never delay(): long work is a state machine
//
// Fixed buffers, no heap: fits small boards.
#pragma once

#include <Arduino.h>

#ifndef LABINT_MAX_FUNCTIONS
#define LABINT_MAX_FUNCTIONS 4
#endif
#ifndef LABINT_MAX_COMMANDS
#define LABINT_MAX_COMMANDS 12
#endif
#ifndef LABINT_MAX_HW
#define LABINT_MAX_HW 4
#endif
#define LABINT_LINE 161  // 160 characters + terminator
#define LABINT_MAX_ARGS 8
#define LABINT_PROTOCOL 1

class LabInt {
 public:
  enum Error : uint8_t {
    ERR_UNKNOWN = 1, ERR_ARGUMENT = 2, ERR_RANGE = 3, ERR_BUSY = 4,
    ERR_NOT_READY = 5, ERR_HARDWARE = 6, ERR_UNSUPPORTED = 7, ERR_AUTH = 8,
  };

  class Function;

  // One outgoing line: "OK fn=photometer bb=5691 …" or "EVT DONE …". Builds in place, send() writes it.
  class Line {
   public:
    Line& kv(const char* key, const char* value);
    Line& kv(const char* key, long value);
    Line& kv(const char* key, unsigned long value);
    Line& kv(const char* key, int value) { return kv(key, (long)value); }
    Line& kv(const char* key, unsigned int value) { return kv(key, (unsigned long)value); }
    Line& kv(const char* key, bool value) { return kv(key, (long)(value ? 1 : 0)); }
    Line& kv(const char* key, double value, uint8_t decimals = 3);
    void send();

   private:
    friend class LabInt;
    void start(LabInt* owner, const char* head);
    void append(const char* text);
    LabInt* owner_ = nullptr;
    char buf_[LABINT_LINE];
    size_t len_ = 0;
    bool overflow_ = false;
  };

  class Request {
   public:
    const char* verb() const { return verb_; }
    Function* function() const { return fn_; }
    uint8_t argc() const { return argc_; }
    const char* arg(uint8_t i) const { return i < argc_ ? argv_[i] : nullptr; }
    // Value of "key=value" among the arguments, or nullptr.
    const char* field(const char* key) const;

    // Typed arguments. On a bad or out-of-range value they send the ERR reply themselves
    // and the request becomes false: `if (!rq) return;`.
    long intArg(uint8_t i, long def, long min, long max);
    double floatArg(uint8_t i, double def, double min, double max);
    const char* strArg(uint8_t i, const char* def = nullptr);

    explicit operator bool() const { return !answered_ || ok_; }
    Line& ok();                             // "OK [fn=…]"; add kv() then send()
    void busy();                            // "BUSY fn=…": the function now runs an operation
    void fail(uint8_t code, const char* message);

   private:
    friend class LabInt;
    LabInt* owner_ = nullptr;
    Function* fn_ = nullptr;
    const char* verb_ = "";
    const char* argv_[LABINT_MAX_ARGS];
    uint8_t argc_ = 0;
    bool answered_ = false;
    bool ok_ = true;
  };

  typedef void (*Handler)(Request&);
  typedef void (*StopHandler)(Line& stoppedEvent);  // add fields to EVT STOPPED (e.g. position)
  typedef void (*ResetHandler)();

  class Function {
   public:
    Function& on(const char* verb, Handler handler);
    Function& hw(const char* key, const char* value);  // answered by HW?
    Function& onStop(StopHandler handler) { stop_ = handler; return *this; }
    Function& onReset(ResetHandler handler) { reset_ = handler; return *this; }
    const char* name() const { return name_; }
    bool busy() const { return busyVerb_[0] != 0; }
    // End the running operation: "EVT DONE fn=… cmd=…"; add kv() then send().
    Line& done();
    // Report a failure of the running operation: "EVT FAULT fn=… cmd=… code=… msg=…".
    void fault(uint8_t code, const char* message);

   private:
    friend class LabInt;
    struct Command { const char* verb; Handler handler; };
    LabInt* owner_ = nullptr;
    const char* name_ = "";
    Command commands_[LABINT_MAX_COMMANDS];
    uint8_t ncommands_ = 0;
    const char* hwKeys_[LABINT_MAX_HW];
    const char* hwValues_[LABINT_MAX_HW];
    uint8_t nhw_ = 0;
    StopHandler stop_ = nullptr;
    ResetHandler reset_ = nullptr;
    char busyVerb_[12] = {0};
  };

  LabInt(const char* firmwareVersion, const char* boardType = nullptr);

  Function& function(const char* name);
  void begin(Stream& link);
  void poll();

  // "EVT <name> [fn=…]"; add kv() then send().
  Line& event(const char* name, Function* fn = nullptr);
  void debug(const char* text);  // "# text": logged by the host

  const char* serial() const { return serial_; }
  const char* name() const { return name_; }

  // Small persistent settings for the sketch: slots 0–31, one byte each.
  uint8_t setting(uint8_t slot, uint8_t def) const;
  void setSetting(uint8_t slot, uint8_t value);

 private:
  friend class Line;
  friend class Request;
  friend class Function;
  void handleLine(char* line);
  bool boardCommand(Request& rq);
  void stopAll(Function* only);
  void write(const char* text);
  void loadIdentity();

  Stream* link_ = nullptr;
  const char* firmware_;
  const char* boardType_;
  Function functions_[LABINT_MAX_FUNCTIONS];
  uint8_t nfunctions_ = 0;
  char in_[LABINT_LINE];
  size_t inLen_ = 0;
  bool inOverflow_ = false;
  Line out_;
  char serial_[17] = {0};
  char name_[25] = {0};
};
