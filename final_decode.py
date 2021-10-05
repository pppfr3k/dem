from datetime import datetime
rname = '/home/pi/Desktop/fpy/res.csv'
height = 14
length = 24
width = 22
saver_file = open(rname,'a') 
saver_file.write(str(height) + str(',') + str(length) + str(',') + str(width) + str(',') + str(datetime.now()) + str(',')
                 + str('\n'))
saver_file.close()