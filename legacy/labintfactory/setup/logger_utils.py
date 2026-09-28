import pathlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


class LoggerSetup:
        def __init__(self,name,*,level):
            self.name=name
            self.level=level
            self.handlers=[]
            self.activation=[]
            
        def load(self):
            
            
            def get_debug_level(level):
                    match level:
                        case 'debug':
                            return 'DEBUG'
                        case 'info':
                            return 'INFO'
                        case 'warning':
                            return 'WARNING'
                        case 'error':
                            return 'ERROR'
                        case 'critical':
                            return 'CRITICAL'
                        case _:
                            return 'INFO'
            
            
            path = pathlib.Path(os.path.join(os.getcwd(), "/tmp/labintfactory"))
            
            path.mkdir(parents=True, exist_ok=True)
            
            filename=f"/tmp/labintfactory/{self.name}.log"
                        
            self.handlers=[
                dict(sink=sys.stderr, level=get_debug_level(self.level)),
                dict(sink=filename, enqueue=True, serialize=True,level=get_debug_level('debug')),
            ]
            self.activation=[("labintfactory", True)]
        
        def activate(self):
            from loguru import logger

            return logger.configure(
                handlers=self.handlers,
                activation=self.activation
            )


