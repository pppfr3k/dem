from tkinter import *

root = Tk()

def center_window(width=300, height=200):
    # get screen width and height
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # calculate position x and y coordinates
    x = (screen_width/2) - (width/2)
    y = (screen_height/2) - (height/2)
    root.geometry('%dx%d+%d+%d' % (width, height, x, y))



center_window(500, 400)

busted_display = Label(root, text="Height Calibrated", font=("arial", "21"))
busted_display.place(x=0, y=0)
root.after(5000, root.destroy)
root.mainloop()

