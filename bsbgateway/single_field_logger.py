import time
import os

from bsb.bsb_fields import fields



class SingleFieldLogger(object):
    interval = 1
    disp_id = 0
    send_get_telegram = None
    
    _last_save_time = 0
    _last_saved_value = None
    _dtype = ''
    _last_was_value = False
    filename = ''
    
    def __init__(o, disp_id, interval=1, atomic_interval=1, send_get_telegram=None, filename=''):
        o.disp_id = disp_id
        o.interval = interval
        o.atomic_interval = atomic_interval
        o.send_get_telegram = send_get_telegram
        # list of fn(prev_val, this_val)
        o.triggers = []
        # list of timestamps when trigger was last fired.
        o.trigger_timestamps = []
        
        o.filename = filename or '%d.trace'%disp_id
        if not os.path.exists(filename):
            o.log_fieldname()
        o.log_interval()
        
    def add_trigger(o, callback, triggertype, param1=None, param2=None):
        '''callback: void fn()
        '''
        def fire_trigger(prev_val, this_val):
            callback(logger=o, 
                     triggertype=triggertype, 
                     param1=param1, 
                     param2=param2, 
                     prev_val=prev_val, 
                     this_val=this_val
            )
        
        if triggertype == 'rising_edge':
            def trigger(prev_val, this_val):
                if prev_val<=param1 and this_val>param1:
                    fire_trigger(prev_val, this_val)
                    return True
                return False
        elif triggertype == 'falling_edge':
            def trigger(prev_val, this_val):
                if prev_val>=param1 and this_val<param1:
                    fire_trigger(prev_val, this_val)
                    return True
                return False
        else:
            raise ValueError('bad trigger type %s'%triggertype)
        o.triggers.append(trigger)
        o.trigger_timestamps.append(0)
        
    def check_triggers(o, timestamp, prev_val, this_val):
        for n in range(len(o.triggers)):
            # dead time of 6 hrs after each trigger event!
            if timestamp >= 6*3600 + o.trigger_timestamps[n]:
                # trigger function returns True if trigger fired
                if o.triggers[n](prev_val, this_val):
                    o.trigger_timestamps[n] = timestamp
        
    def get_now(o):
        return o.atomic_interval * int(time.time() / o.atomic_interval)
        
    def tick(o):
        t = o.get_now()
        if t % o.interval == 0:
            o.send_get_telegram(o.disp_id)
            
    def log_value(o, timestamp, value):
        t = o.atomic_interval * int(timestamp  / o.atomic_interval)
        if t != o._last_save_time + o.interval:
            o.log_new_timestamp(t)
        else:
            o._last_save_time = t
            if o._last_saved_value is not None:
                o.check_triggers(t, o._last_saved_value, value)
        if o._last_saved_value is not None and value == o._last_saved_value:
            o._log_append('~', False)
        else:
            dtype = _get_format(value)
            if dtype != o._dtype:
                o._log_append(':dtype %s'%dtype)
                o._dtype = dtype
            o._log_append('%s'%_serialize_value(value))
        o._last_saved_value = value
            
    def log_fieldname(o):
        fld = fields[o.disp_id]
        o._log_append(':disp_id %d'%o.disp_id)
        o._log_append(':fieldname %s'%fld.disp_name.encode('utf8'))
        
    def log_interval(o):
        o._log_append(':interval %d'%o.interval)
            
    def log_new_timestamp(o, timestamp):
        o._log_append(':time %d'%timestamp)
        o._last_save_time = timestamp
    
    def _log_append(o, txt, linebreak_before=True):
        fh = open(o.filename, 'a')
        if linebreak_before or not o._last_was_value:
            txt = '\n'+txt
        fh.write(txt)
        fh.close()
        o._last_was_value = not (txt.startswith(':') or txt.startswith('\n:'))
        
        
def _get_format(val):
    types = {
        type(None): 'none',
        list: 'hex',
        basestring: 'string',
        float: 'float',
        tuple: 'choice',
    }
    for t in types:
        if isinstance(val, t):
            return types[t]
    return 'unknown'
        
def _serialize_value(val):
    if val is None:
        return ''
    if isinstance(val, list):
        return ''.join(map(chr, val)).encode('hex')
    if isinstance(val, basestring):
        return val
    if isinstance(val, float):
        return '%g'%val
    if isinstance(val, tuple):
        return '%g'%val[0]