#include <AccelStepper.h>
#include <EEPROM.h>
#include "./eepromutils.h"

#define EN_PIN 4
#define DIR_PIN 5
#define STEP_PIN 6
#define PULSE 6400
#define CLOCKWISE 1
#define COUNTERCLOCKWISE 0
#define STOP_ONE 2
#define STOP_TWO 3
#define VALIDFLAG 125
#define DELTAT 250
#define UNOR3  3
#define UNOR4  4
#define BOARDTYPE 3
#define MAX_SPEED 3000.0
#define ONE_TURN 6400
#define SERIAL_SPEED 9600


const int cmd_HANDSHAKE = 'h';
const int cmd_GO_HOME1 = 'w';
const int cmd_GO_HOME2 = 'x';
const int cmd_CALIBRATE = 'c';
const int cmd_PING = 'p';
const int cmd_MOVE_FORWARD = 'f';
const int cmd_MOVE_BACKWARD = 'b';
const int cmd_SEND_MOVEMENT_FORWARD = 'm';
const int cmd_SEND_MOVEMENT_BACKWARD= 'q';
const int cmd_GET_POSITION = 'g';
const int cmd_GET_MAX_POSITION ='a';
const int cmd_GO_POSITION = 'u';
const int cmd_GET_STOP_STATUS ='e';
const int cmd_SET_MAX_POSITION = 't';
const int cmd_SET_POSITION = 'k';
const int cmd_IS_CALIBRATED = 'r';
const int cmd_REBOOT =  'z';
const int cmd_DEBUG = 'd';
const int cmd_CLEAN_BUFFER='y';
const int cmd_PRINT_DATA='j';
const int cmd_SET_SPEED='s';
const int cmd_GET_SPEED='i';
const int cmd_DISABLE='n';
const int cmd_ENABLE='o';
const int cmd_SET_CALIBRATED='l';


const int min_step=80;
const float resolution=0.1;

String data;
volatile bool running = true;
char command;
bool writeflag=false;
bool debug=false;

long  lastwrite=0;
long  move_position=0;
unsigned int current_address=0;

struct arm_configuration {
  int validdata;                    
  bool calibrated;
  long position;                   // last cart position
  long max_position;
  float speed;
  bool enabled;
  
};

arm_configuration myarm;


AccelStepper nema23(AccelStepper::DRIVER, STEP_PIN, DIR_PIN,false);

void print_data(){
    Serial.print("valid_flag:");
    Serial.println(myarm.validdata);
    Serial.print("calibration_status:");
    Serial.println(myarm.calibrated);
    Serial.print("current_position:");
    Serial.println(myarm.position);
    Serial.print("max_position:");
    Serial.println(myarm.max_position);
    Serial.print("speed:");
    Serial.println(myarm.speed);
    Serial.print("motor_enabled:");
    Serial.println(myarm.enabled);
    Serial.println("executed");
}

template <class T> void debug_print(T param)
{
   if(debug){
    Serial.print(param);
   }
}
template <class T> void debug_println(T param)
{
   if(debug){
    Serial.println(param);
   }
}

void set_defaults(){
    myarm.validdata=0;
    myarm.calibrated=false;
    myarm.position=0;
    myarm.max_position=0;
    myarm.speed=1000.0;
    myarm.enabled=false;
}

void invalidate_eeprom(){
    int datasize;
    datasize = sizeof(myarm);
    myarm.validdata=0;//invalidate current data location
    EEPROM_writeAnything(current_address, myarm);//write invalidated data
    current_address += datasize;
    debug_print("Eeprom invalidated!");
}

void write_eeprom(){
    EEPROM_writeAnything(current_address, myarm);
    writeflag=false;
}

void setup() {
  int datasize;    // will hold size of the struct myarm
  int nlocations;
  current_address=0;
  bool found=false;
  lastwrite=millis();
  Serial.begin(SERIAL_SPEED);
  
  //stepper.setPinsInverted(false, false, true);
  nema23.setMaxSpeed(MAX_SPEED);
  nema23.setAcceleration(1);
  
  nema23.setMinPulseWidth(20);

  //stepper.enableOutputs()
  
  nema23.setPinsInverted(false,false,true);


  nema23.setEnablePin(EN_PIN);

  nema23.disableOutputs();

  pinMode(STOP_ONE, INPUT);
  attachInterrupt(digitalPinToInterrupt(STOP_ONE), homestop, CHANGE);
  attachInterrupt(digitalPinToInterrupt(STOP_TWO), homestop, CHANGE);
  running=digitalRead(STOP_ONE)||digitalRead(STOP_TWO);
  
  datasize = sizeof(myarm);
  nlocations = EEPROM.length() / datasize;

  for (int lp1 = 0; lp1 < nlocations; lp1++) {
    int addr = lp1 * datasize;
    EEPROM_readAnything(addr, myarm);
    
    if (myarm.validdata==VALIDFLAG) {
      
      current_address = addr;
      found = true;
      break;
    }
  }
  while (!Serial) { delay(50); }
  
  if (found){
    EEPROM_readAnything(current_address, myarm);//read current data
    myarm.validdata=0;//invalidate current data location
    EEPROM_writeAnything(current_address, myarm);//write invalidated data
    current_address += datasize;
    
    if (current_address >= (nlocations * datasize)) {
      current_address = 0; //loop back eeprom locations
    }
    myarm.validdata = VALIDFLAG;
    EEPROM_writeAnything(current_address, myarm);
    myarm.enabled=false;
    print_data();
  }else{
    debug_println("No valid data found");
    set_defaults();
    print_data();
    write_eeprom();
  }
  Serial.flush();

  nema23.setCurrentPosition(myarm.position);

}

int move(bool rotation,unsigned long microsteps,uint8_t stop,uint16_t pulse){

          if (!myarm.enabled){
            Serial.println("Motor disabled");
            return 0;
            }

          int i=0;
          if ((myarm.validdata==125)&& (!writeflag)){
              invalidate_eeprom();
          }
   
          long inc =(rotation)?1:-1;

          running=digitalRead(stop);

          move_position=myarm.position+inc*microsteps;
            

          Serial.println("Start movement");

          if ((move_position > myarm.max_position)|| (move_position<0)){
              Serial.println("Cannot move");
              return 0;
            }

          if (running) {
              nema23.setSpeed(inc*abs(myarm.speed));
              
              while ((i<microsteps)&& running){ 
                  if (nema23.runSpeed()){
                     myarm.position+=inc;
                     i++;
                  }

              }
          }
          writeflag=true;
          return 1;
}


void go_home(char side, uint16_t pulse, uint8_t stop){

    if (!myarm.enabled){
            Serial.println("Motor disabled");
            return 0;
            }
    
    nema23.setMaxSpeed(6000);


    if ((myarm.validdata==125)&& (!writeflag)){
              invalidate_eeprom();
          }

    int i=0;
    running=digitalRead(stop);
    long inc;
    inc = (side=='m')?-1:1;

    if (side=='m'){
      Serial.println("Going home, motor side.");
    }else{
      Serial.println("Going home, other side.");
    }
    
    
    
    if (running) {
      

      nema23.setSpeed(inc*5000);
      
      while (running){

        if (nema23.runSpeed()){
             myarm.position+=inc;
            }
        }
      running=true;
      
      delayMicroseconds(2000);
      nema23.setSpeed(-inc*5000);
      
      while ((i<8*min_step)){ 
                  if (nema23.runSpeed()){
                     myarm.position-=inc;
                     i++;
                  }

              }      
    }
    writeflag=true;
    nema23.setMaxSpeed(MAX_SPEED);
  }



void loop() {


if( (writeflag) && (millis()-lastwrite>DELTAT)){ 

      myarm.validdata=VALIDFLAG;
      debug_print("Write data to eeprom at address: ");
      debug_println(current_address);
      write_eeprom();
      lastwrite=millis();
      writeflag=false;

}
  

if (Serial.available()) {
    command = Serial.read();
    switch (command) {
      case cmd_SET_CALIBRATED:
        myarm.calibrated=true;
        Serial.println("executed");
        break;

      case cmd_DISABLE:
        nema23.disableOutputs();
        myarm.enabled=false;
        Serial.println("executed");
        break;
      case cmd_ENABLE:
        nema23.enableOutputs();
        myarm.enabled=true;
        Serial.println("executed");
        break;
      case cmd_CLEAN_BUFFER:
            serialFlush();
            Serial.println("executed");
            break;
      case cmd_PRINT_DATA:
        print_data();
        break;
      case cmd_REBOOT:
        reboot();
        break;
      case cmd_IS_CALIBRATED:
        Serial.println(myarm.calibrated);
        Serial.println("executed");
        break;
      case cmd_SET_POSITION:
        data=Serial.readString();
        myarm.position=data.toInt();
        writeflag=true;
        Serial.println("executed");
        break;
      case cmd_GET_SPEED:
        Serial.println(myarm.speed);
        Serial.println("executed");
        break;
      case cmd_SET_SPEED:
        data=Serial.readString();
        myarm.speed=data.toFloat();
        writeflag=true;
        Serial.println("executed");
        break;
      case cmd_SET_MAX_POSITION:
        data=Serial.readString();
        myarm.max_position=data.toInt();
        writeflag=true;
        Serial.println("executed");
        break;
      case cmd_GET_STOP_STATUS:
        Serial.print(digitalRead(STOP_ONE));
        Serial.print(",");
        Serial.println(digitalRead(STOP_TWO));
        Serial.println("executed");
        break;  

      case cmd_GO_POSITION:
          data=Serial.readString();
          move_position=data.toInt();
          
          if ((move_position<=myarm.max_position)&& (move_position>=0)){
              if (move_position>=myarm.position){
                  move(CLOCKWISE,move_position-myarm.position,STOP_TWO,PULSE);
              }else{
                  move(COUNTERCLOCKWISE,myarm.position-move_position,STOP_ONE,PULSE);
              }

          }
          Serial.println("executed");
        break;
      case cmd_GET_POSITION:
        Serial.println(myarm.position);
        Serial.println("executed");
        break;
      case cmd_GET_MAX_POSITION:
        Serial.println(myarm.max_position);
        Serial.println("executed");
        break;
      
      case cmd_CALIBRATE:
         
         go_home('m',PULSE,STOP_ONE);
         myarm.position=0;
         go_home('o',PULSE,STOP_TWO);
         myarm.max_position=myarm.position;
         Serial.print("Max Position: ");
         Serial.println(myarm.max_position);
         Serial.println("executed");
         myarm.calibrated=true;
         
         break;
      
      case cmd_GO_HOME1:
         go_home('m',PULSE,STOP_ONE);
         Serial.println("executed");
         Serial.flush();
         break;    
      
      case cmd_GO_HOME2:
        go_home('o',PULSE,STOP_TWO);
        Serial.println("executed");
        Serial.flush();
        break;    

      case cmd_MOVE_FORWARD:
        if (is_not_calibrated()){break;}
        Serial.println("Move forward 1 turn");
        move(CLOCKWISE,ONE_TURN,STOP_TWO,PULSE);
        Serial.println("executed");
        break;

      case cmd_SEND_MOVEMENT_FORWARD:
          if (is_not_calibrated()){break;}
          data=Serial.readString();
          move(CLOCKWISE,floor((data.toFloat())/resolution)*min_step,STOP_TWO,PULSE);
          Serial.println("executed");        
        break;

      case cmd_SEND_MOVEMENT_BACKWARD:
          if (is_not_calibrated()){break;}
          data=Serial.readString();
          move(COUNTERCLOCKWISE,floor((data.toFloat())/resolution)*min_step,STOP_ONE,PULSE);
          Serial.println("executed");     
        break;

       case cmd_MOVE_BACKWARD:
          if (is_not_calibrated()){
          Serial.println("Not calibrated");
          break;}        
         Serial.println("Move backwards 1 turn");
         move(COUNTERCLOCKWISE,ONE_TURN,STOP_ONE,PULSE);
         Serial.println("executed");
        break; 
   
      case cmd_HANDSHAKE:
        handshake();
        Serial.println("executed");
        break;
      
      case cmd_PING:
        Serial.println("PONG");
        Serial.println("executed");
        break;

      case cmd_DEBUG:
        debug=!debug;

        if (is_not_calibrated()){
          Serial.println("Not calibrated");
        }else{
          Serial.println("Calibrated");
        }

        if (debug){
          debug_println("Debug enabled");
        } else{
           Serial.println("Debug disabled");
        }
        Serial.println("executed");
        break;      
      
      }
  }

}

void serialFlush(){
  while(Serial.available() > 0) {
    char t = Serial.read();
  }
}

bool is_not_calibrated(){
    if (!myarm.calibrated){
            Serial.println("not calibrated");
            Serial.println("executed");
        } 
    return !myarm.calibrated;
}

void reboot() {
  #if (BOARDTYPE==UNOR4)
    NVIC_SystemReset();
  #else
   asm volatile("jmp 0");
  #endif
  
}

void homestop() {
 running=false;
}

void handshake() {
  Serial.println('R');
  Serial.flush();
}