#!/bin/bash

{ 
## #Convert pdf to png
	convert $1 -flatten -colorspace RGB miff:-; \
   	convert $2 -flatten -colorspace RGB miff:-; 
} |
{ 
## #Create diff mask and convert to grayscale png

#	convert - -write mpr:AB \
#		-delete 0--1 \
#		\( mpr:AB[0] mpr:AB[1] -compose difference -composite -threshold 0 \
#	   		-separate -evaluate-sequence Add \) \
#		\( mpr:AB[0] -colorspace gray \) \
#		\( mpr:AB[1] -colorspace gray \) \
#		miff:-; 
## Replaced with
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[0] mpr:AB[1] -compose difference -composite \) \
		\( mpr:AB[0] -colorspace gray \) \
		\( mpr:AB[1] -colorspace gray \) \
		miff:-; 
} |
{ 
## #Colorize sources
	convert - -write mpr:AB \
		-delete 0--1 \
		mpr:AB[0] \
		\( mpr:AB[1] \( mpr:AB[1] -fill orange -colorize 100 \) \
			-compose blend -composite \) \
		\( mpr:AB[2] \( mpr:AB[2] -fill green -colorize 100 \) \
			-compose blend -composite \) \
		miff:-;
} |
{
## #Create colorized masks
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -alpha Off -compose CopyOpacity -composite \) \
		\( mpr:AB[2] mpr:AB[0] -alpha Off -compose CopyOpacity -composite \) \
		miff:-; 
} |
{
## #Multiply diffs
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -compose multiply -composite \) \
		miff:-; 
} |
## #Compose lighten source with diff
	#convert \( $1 +level-colors "#e0e0e0", \) - -composite miff:- |
	convert \( $1 -flatten -fill white -colorize 80%, \) - -composite miff:- |
		display
	## Save as file:
	##	${1%.*}-${2%.*}_diff.png;
