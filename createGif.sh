#!/bin/bash

if [ -d frames ]; then
	rm -r frames; fi

NOW=$(date +"%Y%m%d%H%M%S")
SIZE=100
GIF_PARTS=""

##wmctrl -r :SELECT: -e 0,342,282,1024,742
mkdir frames
ffmpeg -i $1 -r 10 frames/ffout%04d.png
cd frames
##ffmpeg -f x11grab -framerate 10 -video_size 1024x742 -i $DISPLAY+342,282  -pix_fmt rgb24 ffout%04d.png
NO_FILES=$(ls | wc -l)
NO_PARTS=$(expr $NO_FILES / $SIZE)
for i in $(seq -w 00 $NO_PARTS); do
	convert -verbose -delay 10 ffout$i??.png -layers optimize part_$i.gif
	GIF_PARTS+="frames/part_$i.gif "; done
cd ..

## To create "..." between loops
##convert -verbose -size 1024x742 -dispose none xc:white -set delay 75 \
##	-gravity center -pointsize 480 -font /home/mf/.local/share/fonts/OpenSans-Bold.ttf \
##	-annotate +0+0 '...' -dispose none -delay 75 xc:white -loop 0 tmp.gif

convert -verbose tmp.gif tmp.gif tmp.gif tmp.gif $GIF_PARTS _$NOW.gif
###convert -verbose tmp.gif tmp.gif tmp.gif tmp.gif start.gif $GIF_PARTS end.gif _$NOW.gif
gifsicle -V -O2 --colors 256 _$NOW.gif -o $NOW.gif
rm _$NOW.gif

## PNG sequence to animated gif
## convert -verbose -delay 4 -loop 0 *.png output.gif
