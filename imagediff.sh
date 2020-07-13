#!/bin/bash

{ 
## #Convert pdf to png
	convert -density $3 $1 -flatten -colorspace RGB miff:-; \
	convert -density $3 $2 -flatten -colorspace RGB miff:-; \
} |
## mpr:A[0] -> first image rasterized
## mpr:A[1] -> second image rasterized
{ 
## #Create diff mask and convert to grayscale png
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[0] mpr:AB[1] -compose difference -composite \) \
		\( mpr:AB[0] -colorspace gray \) \
		\( mpr:AB[1] -colorspace gray \) \
		mpr:AB[0] \
		miff:-; 
} |
## mpr:A[0] -> diff mask
## mpr:A[1] -> first image grayscaled 
## mpr:A[2] -> second image grayscaled 
## mpr:A[3] -> first image rasterized
{ 
## #Colorize sources
	convert - -write mpr:AB \
		-delete 0--1 \
		mpr:AB[0] \
		\( mpr:AB[1] \( mpr:AB[1] -fill '#cc6600' -colorize 100 \) \
			-compose blend -composite \) \
		\( mpr:AB[2] \( mpr:AB[2] -fill '#800000' -colorize 100 \) \
			-compose blend -composite \) \
		mpr:AB[3] \
		miff:-;
} |
## mpr:A[0] -> diff mask
## mpr:A[1] -> first image colorized (yellow) 
## mpr:A[2] -> second image colorized (red) 
## mpr:A[3] -> first image rasterized 
{
## #Create colorized masks
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -alpha Off -compose CopyOpacity -composite \) \
		\( mpr:AB[2] mpr:AB[0] -alpha Off -compose CopyOpacity -composite \) \
		mpr:AB[3] \
		mpr:AB[0] \
		miff:-; 
} |
## mpr:A[0] -> first image colorized mask
## mpr:A[1] -> second image colorized mask
## mpr:A[2] -> first image rasterized 
## mpr:A[3] -> diff mask
{
## #Multiply diffs
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -compose multiply -composite \) \
		mpr:AB[2] \
		mpr:AB[3] \
		miff:-; 
} | 
## mpr:A[0] -> colorized diff
## mpr:A[1] -> first image rasterized 
## mpr:A[2] -> diff mask
{
## #Clean the source
	convert - -write mpr:AB \
		-delete 0--1 \
		mpr:AB[0] \
		\( mpr:AB[1] mpr:AB[2] -compose plus -composite \) \
		miff:-;
} |
## mpr:A[0] -> colorized diff
## mpr:A[1] -> first image cleaned 
{
## #Compose the cleaned source with diff
	convert - -write mpr:AB \
		-delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -composite \) \
		miff:-;
} |
	display
#	## Save as file:
#	##	${1%.*}-${2%.*}_diff.png;
