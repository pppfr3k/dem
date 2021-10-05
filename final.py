# importing required modules
from time import sleep
from time import time
import RPi.GPIO as GPIO
import picamera
import cv2
import imutils
from imutils import perspective
from scipy.spatial import distance as dist
import numpy as np
import os
from serial import Serial
import tkinter as tk
from PIL import Image, ImageTk
from gpiozero import Button
from tkinter import messagebox
from datetime import datetime

serialPort = "/dev/ttyAMA0" # default for RaspberryPi
maxwait = 3

def midpoint(ptA,ptB):
    return ((ptA[0] + ptB[0]) * 0.5, (ptA[1] + ptB[1]) * 0.5)

def shadow_removal(image):
    channels = cv2.split(image)
    result_channels = []
    result_norm_channels = []
    for channel in channels:
        dilated_img = cv2.dilate(channel, np.ones((3,3), np.uint8))
        bg_img = cv2.medianBlur(dilated_img, 3)
        diff_img = 255 - cv2.absdiff(channel, bg_img)
        result_channels.append(diff_img)

    result = cv2.merge(result_channels)
    return result

def gray(image):
    return cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)

def detect_contour(image):
    # converting into gray and blur
    #gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    #gray = cv2.GaussianBlur(gray,(3,3),0)
    # detecting edges and dilate and erode to cover gaps
    edge = cv2.Canny(image,50,100)
    edge = cv2.dilate(edge,None,iterations=1)
    edge = cv2.erode(edge,None,iterations=1)
    # detecting contours
    cnts = cv2.findContours(edge.copy(),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    return cnts

def bounding_boxes(image,cnts):
    orig = image.copy()
    dimensions = []
    for c in cnts:
        if cv2.contourArea(c)<100:
            continue
        box = cv2.minAreaRect(c)
        box = cv2.boxPoints(box)
        box = np.array(box,dtype='int')
        box = perspective.order_points(box)
        # drawing bounding box
        cv2.drawContours(orig, [box.astype("int")], -1, (0, 255, 0), 2)
        # drawing the vetices
        for (x, y) in box:
            cv2.circle(orig, (int(x), int(y)), 3, (0, 0, 255), -1)
        (tl, tr, br, bl) = box
        # getting midpoints of the edges
        (tltrX, tltrY) = midpoint(tl, tr)
        (blbrX, blbrY) = midpoint(bl, br)
        (tlblX, tlblY) = midpoint(tl, bl)
        (trbrX, trbrY) = midpoint(tr, br)
        # drawing midpoints
        cv2.circle(orig, (int(tltrX), int(tltrY)), 2, (255, 0, 0), -1)
        cv2.circle(orig, (int(blbrX), int(blbrY)), 2, (255, 0, 0), -1)
        cv2.circle(orig, (int(tlblX), int(tlblY)), 2, (255, 0, 0), -1)
        cv2.circle(orig, (int(trbrX), int(trbrY)), 2, (255, 0, 0), -1)
        # drawing lines between midpoints
        # cv2.line(orig, (int(tltrX), int(tltrY)), (int(blbrX), int(blbrY)), (255, 0, 255), 2)
        # cv2.line(orig, (int(tlblX), int(tlblY)), (int(trbrX), int(trbrY)), (255, 0, 255), 2)
        # getting pixel lengths
        dA = dist.euclidean((tltrX, tltrY), (blbrX, blbrY))
        dB = dist.euclidean((tlblX, tlblY), (trbrX, trbrY))
        # writing pixel values
        # cv2.putText(orig, "{}px".format(dA), (int(tltrX - 15), int(tltrY - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        # cv2.putText(orig, "{}px".format(dB), (int(trbrX + 10), int(trbrY)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        #pixel_lengths = []
        pixel_lengths = [dA,dB]
    try:
        return orig,pixel_lengths
    except:
        print('retrying')
        return orig,[0,0]
    
# funtion to compute distance between sensor and object
def measure(portName):
    ser = Serial(portName, 9600, 8, 'N', 1, timeout=1)
    timeStart = time()
    valueCount = 0

    while time() < timeStart + maxwait:
        if ser.inWaiting():
            bytesToRead = ser.inWaiting()
            valueCount += 1
            if valueCount < 2: # 1st reading may be partial number; throw it out
                continue
            testData = ser.read(bytesToRead)
            if not testData.startswith(b'R'):
                # data received did not start with R
                continue
            try:
                sensorData = testData.decode('utf-8').lstrip('R')
            except UnicodeDecodeError:
                # data received could not be decoded properly
                continue
            try:
                mm = int(sensorData)
            except ValueError:
                # value is not a number
                continue
            ser.close()
            return(mm)

    ser.close()
    raise RuntimeError("Expected serial data not received")

class MainWindow():
    def __init__(self, window, cap, button, button1):
        print('deb')
        self.window = window
        self.window.state("normal")
        self.window.title('Volume of object')
        self.cap = cap
        self.cap.preview_fullscreen = False
        self.cap.preview_window = (90,100,320,240)
        self.cap.resolution = (640,480)
        #self.cap.start_preview()
        
        windowWidth = window.winfo_reqwidth()
        windowHeight = window.winfo_reqheight()
        # Gets both half the screen width/height and window width/height
        positionRight = int(window.winfo_screenwidth()/2 - 1.6*windowWidth)
        positionDown = int(window.winfo_screenheight()/2 - windowHeight/1.6)
        # Positions the window in the center of the page.
        window.geometry("+{}+{}".format(positionRight, positionDown))
        
        #getting screen width and height of display
#         self.winwidth= window.winfo_screenwidth()
#         self.winheight= window.winfo_screenheight()
        #setting tkinter window size
#         self.window.geometry("%dx%d" % (self.winwidth/1.5, self.winheight/2))
        #self.window.eval('tk::PlaceWindow . center')


        self.width = 0
        self.height = 0
        self.length = 0
        self.volume = 0
        self.vweight = 0
        
        lbl = tk.Label(self.window, text="Height:",font=('Arial', 25))
        lbl.grid(column=0, row=0)
        lbl = tk.Label(self.window, text="Length:",font=('Arial', 25))
        lbl.grid(column=0, row=1)
        lbl = tk.Label(self.window, text="Width:",font=('Arial', 25))
        lbl.grid(column=0, row=2)
        lbl = tk.Label(self.window, text="Volume:",font=('Arial', 25))
        lbl.grid(column=0, row=3)
        lbl = tk.Label(self.window, text="Volume Weight:",font=('Arial', 25))
        lbl.grid(column=0, row=4)
        lbl = tk.Label(self.window, text="Actual Weight:",font=('Arial', 25))
        lbl.grid(column=0, row=5)
        self.lbl1 = tk.Label(self.window,text= 'height',font=('Arial', 25))
        self.lbl1.grid(column=1, row=0)
        self.lbl2= tk.Label(self.window, text= 'length' ,font=('Arial', 25))
        self.lbl2.grid(column=1, row=1)
        self.lbl3= tk.Label(self.window, text= 'width' ,font=('Arial', 25))
        self.lbl3.grid(column=1, row=2)
        self.lbl4= tk.Label(self.window, text= 'volume',font=('Arial', 25))
        self.lbl4.grid(column=1, row=3)
        self.lbl5= tk.Label(self.window, text= 'volumetric weight',font=('Arial', 25))
        self.lbl5.grid(column=1, row=4)
        self.lbl6= tk.Label(self.window, text= 'actual weight',font=('Arial', 25))
        self.lbl6.grid(column=1, row=5)
        self.interval = 10 # Interval in ms to get the latest frame
        self.button = button
        self.button1 = button1
        
        self.bc1 = 1
        self.bc2 = 1

        # Create canvas for image
        self.canvas = tk.Label(self.window, ) # width=self.width, height=self.height
        self.canvas.grid(row=7, column=0, rowspan = 10)

        self.update_image()


    def update_image(self):

        if self.button1.is_pressed:
        #if GPIO.input(5) == 1:
        #if self.bc1 == 1:
            calibrate_file = open("/home/pi/Desktop/fpy/hfiles/c.txt",'w')
            calibrate_file.write(str(measure("/dev/ttyAMA0")))
            calibrate_file.close()
            self.bc1 = 2
            print('11')
            os.system("python3 /home/pi/Desktop/fpy/hfeed.py")

        if self.button.is_pressed:
        #if GPIO.input(27) == 1:
        #if self.bc2 == 1:
            # Get the latest frame and convert image format
            self.image = np.empty((640 * 480 * 3,), dtype=np.uint8)
            self.cap.capture(self.image, 'bgr')
            self.image = self.image.reshape((480, 640, 3))
            self.image = self.image[210:420,100:550]
            shad = shadow_removal(self.image)
            grayed = gray(shad)
            cnts = detect_contour(grayed)
            self.image,dimensions = bounding_boxes(self.image,cnts)
            #self.image,dimensions, gflag = bounding_boxes(self.image,cnts)
            #while True:
             #   if gflag == 0:
              #      break
               # else:
                    #messagebox.showwarning("Warning","Camera placed incorrectly, retrying every 5 seconds")
                   # sleep(5)
                    
            self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
            imgnpz = self.image# to RGB
            self.image = Image.fromarray(self.image) # to PIL format
            self.image = ImageTk.PhotoImage(self.image) # to ImageTk format
            cfile = open("/home/pi/Desktop/fpy/hfiles/c.txt",'r')
            #cnu#ms = cfile.readlines()
            #cthresh = [int(i) for i in cnums]
            cthresh = int(cfile.read())
            print(cthresh)
            cfile.close()
            #self.height = np.floor((cthresh- int(measure("/dev/ttyAMA0")))/10)
            buff_h = int(measure("/dev/ttyAMA0"))
            sconst = 0.000193
            self.height = round((cthresh- buff_h)/10,2)
            self.width =  round(dimensions[0]*buff_h*sconst,2)
            self.length = round(dimensions[1]*buff_h*sconst,2)
            #self.width = np.floor((dimensions[0]*cthresh -(-8.0572)*cthresh - (-57.3632)*dimensions[0] - 9173.6329)/(556.966))
            #self.length = np.floor((dimensions[1]*cthresh -(-8.0572)*cthresh - (-57.3632)*dimensions[1] - 9173.6329)/(556.966))
            self.volume = round(self.height*self.length*self.width,2)
            self.vweight = round(self.volume/5000,2)
            #array_res = np.array([self.height,self.length,self.width,self.volume,self.vweight])
            array_res = [self.height,self.length,self.width,self.volume,self.vweight]         


            if(self.height <= 0 or self.length <= 0 or self.width <= 0):
                print("Retrying")
                #messagebox.showwarning("Warning","Invalid Camera input, retrying every 5 seconds")
                #sleep(5)
                os.system("python3 /home/pi/Desktop/fpy/warn_feed.py")
            else:
                counter_file = open("/home/pi/Desktop/fpy/hfiles/cnt.txt",'r') #initiate file with 0
                counter_val = int(counter_file.read())
                print(counter_val)
                fname = '/home/pi/Desktop/fpy/res/id' + str(counter_val)
                imname = fname + 'img.jpeg'
                rname = '/home/pi/Desktop/fpy/res/res.csv'
                
                dmim = Image.fromarray(imgnpz)
                dmim.save(imname)
                
                saver_file = open(rname,'a') 
                saver_file.write(str(self.height) + str(',') + str(self.length) + str(',') + str(self.width) + str(',') + str(self.volume) + str(',') + str(self.vweight) + str(',') + str(datetime.now()) + str(',')+ str('\n'))
                saver_file.close()
                
                #np.save(imname, imgnpz)
                #np.save(rname, array_res)
                counter_file.close()
            
                counter_file = open("/home/pi/Desktop/fpy/hfiles/cnt.txt",'w')
                counter_file.write(str(counter_val + 1))
                counter_file.close()
              
            self.lbl1['text'] = str(self.height) + 'cm'
            self.lbl2['text'] = str(self.length) + 'cm'
            self.lbl3['text'] = str(self.width) + 'cm'
            self.lbl4['text'] = str(self.volume) + 'cm3'
            self.lbl5['text'] = str(self.vweight) + 'cm3'
            self.lbl6['text'] = str('Not Connected')
        # Update image
        #self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image)
            self.canvas.imgtk = self.image
            self.canvas.configure(image=self.image)
            self.bc2 = 2

        self.window.after(self.interval,self.update_image)


if __name__ == '__main__':

    root = tk.Tk()
    button = Button(25)
    button1 = Button(5)
    #GPIO.setup(25, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    #GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print('0')
    os.system("python3 /home/pi/Desktop/fpy/guifeed.py")
    wind = MainWindow(root, picamera.PiCamera(),button, button1)
    print('1')
    root.mainloop()
    
    #camera = picamera.PiCamera()
    #mm = measure(serialPort)
    #print('distance = {}'.format(mm))
