"""GNOME/X11 window placement and a single EWMH focus request; no polling refocus."""
import ctypes as C
import ctypes.util


# Window handles may disappear between enumeration and a property read.
_ERROR_HANDLER=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p)(lambda _display,_error:0)


class ClientMessage(C.Structure):
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),
              ('display',C.c_void_p),('window',C.c_ulong),('message_type',C.c_ulong),
              ('format',C.c_int),('data',C.c_long*5)]


class Event(C.Union):
    _fields_=[('message',ClientMessage),('pad',C.c_long*24)]


class Window:
    def __init__(self):
        self.x=C.CDLL(ctypes.util.find_library('X11'))
        self.x.XSetErrorHandler.argtypes=[C.c_void_p]
        self.x.XSetErrorHandler(_ERROR_HANDLER)
        self.x.XOpenDisplay.argtypes=[C.c_char_p]; self.x.XOpenDisplay.restype=C.c_void_p
        self.x.XDefaultRootWindow.argtypes=[C.c_void_p]; self.x.XDefaultRootWindow.restype=C.c_ulong
        self.x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int]; self.x.XInternAtom.restype=C.c_ulong
        self.x.XGetWindowProperty.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_long,C.c_long,C.c_int,
            C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_ulong),
            C.POINTER(C.c_ulong),C.POINTER(C.c_void_p)]
        self.x.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)]
        self.x.XFlush.argtypes=[C.c_void_p]
        self.x.XFree.argtypes=[C.c_void_p]
        self.x.XCloseDisplay.argtypes=[C.c_void_p]
        self.display=self.x.XOpenDisplay(None)
        if not self.display: raise ValueError('Cannot connect to the X11 desktop.')
        self.root=self.x.XDefaultRootWindow(self.display)

    def atom(self,name):
        return self.x.XInternAtom(self.display,name.encode(),False)

    def prop(self,window,name):
        actual,fmt,count,left,pointer=C.c_ulong(),C.c_int(),C.c_ulong(),C.c_ulong(),C.c_void_p()
        result=self.x.XGetWindowProperty(self.display,window,self.atom(name),0,16384,False,0,
            C.byref(actual),C.byref(fmt),C.byref(count),C.byref(left),C.byref(pointer))
        if result or not pointer.value: return None
        try:
            if fmt.value==32:
                return list(C.cast(pointer,C.POINTER(C.c_ulong))[:count.value])
            if fmt.value==8:
                return C.string_at(pointer,count.value).decode('utf-8','replace')
        finally: self.x.XFree(pointer)
        return None

    def active(self):
        return (self.prop(self.root,'_NET_ACTIVE_WINDOW') or [0])[0]

    def find_role(self,role):
        for handle in self.prop(self.root,'_NET_CLIENT_LIST') or []:
            if self.prop(handle,'WM_WINDOW_ROLE') == role: return handle
        return None

    def send(self,handle,name,values):
        event=Event()
        event.message=ClientMessage(33,0,1,self.display,handle,self.atom(name),32,(C.c_long*5)(*values))
        self.x.XSendEvent(self.display,self.root,False,(1<<19)|(1<<20),C.byref(event))
        self.x.XFlush(self.display)

    def focus(self,handle):
        self.send(handle,'_NET_ACTIVE_WINDOW',[2,0,self.active(),0,0])

    def rectangle(self,mode):
        areas=self.prop(self.root,'_NET_WORKAREA') or [0,0,1280,720]
        desktop=(self.prop(self.root,'_NET_CURRENT_DESKTOP') or [0])[0]
        offset=desktop*4
        x,y,w,h=areas[offset:offset+4] if len(areas)>=offset+4 else areas[:4]
        if mode=='side': return x+w*2//3,y,max(1,w//3),h
        if mode=='top': return x,y,w,max(1,h//3)
        width,height=max(1,w*4//5),max(1,h*4//5)
        return x+(w-width)//2,y+(h-height)//2,width,height

    def place(self,handle,mode):
        self.send(handle,'_NET_MOVERESIZE_WINDOW',[10|0xf00|(2<<12),*self.rectangle(mode)])

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display);self.display=None
