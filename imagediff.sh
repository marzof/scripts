#!/bin/bash

FILENAME=${1%.*}-${2%.*};
## Add this to get file output during the process
# tee >(convert - $FILENAME.png) |

## #Convert pdf to png (direct convert creates artifacts for large images)
## Output:
## -[0] -> first image rasterized
## -[1] -> second image rasterized
{ 
	pdftoppm -png -rx $3 -ry $3 $1 | convert - -flatten -colorspace RGB miff:-; \
	pdftoppm -png -rx $3 -ry $3 $2 | convert - -flatten -colorspace RGB miff:-; \
} |

## #Create diff mask and convert to grayscale png
## Output:
## mpr:A[0] -> diff mask
## mpr:A[1] -> first image grayscaled 
## mpr:A[2] -> second image grayscaled 
## mpr:A[3] -> first image rasterized
{ 
	convert - -write mpr:AB -delete 0--1 \
		\( mpr:AB[0] mpr:AB[1] -compose difference -composite \) \
		\( mpr:AB[0] -colorspace gray \) \
		\( mpr:AB[1] -colorspace gray \) \
		mpr:AB[0] \
		miff:-; 
} |

## #Colorize sources
## Output:
## mpr:A[0] -> diff mask
## mpr:A[1] -> first image colorized (yellow) 
## mpr:A[2] -> second image colorized (red) 
## mpr:A[3] -> first image rasterized 
{ 
	convert - -write mpr:AB -delete 0--1 \
		mpr:AB[0] \
		\( mpr:AB[1] \( mpr:AB[1] -fill '#cc6600' -colorize 100 \) \
			-compose blend -composite \) \
		\( mpr:AB[2] \( mpr:AB[2] -fill '#800000' -colorize 100 \) \
			-compose blend -composite \) \
		mpr:AB[3] \
		miff:-;
} |

## #Create colorized masks
## Output:
## mpr:A[0] -> first image colorized mask
## mpr:A[1] -> second image colorized mask
## mpr:A[2] -> first image rasterized 
## mpr:A[3] -> diff mask
{
	convert - -write mpr:AB -delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -alpha Off -compose CopyOpacity -composite \) \
		\( mpr:AB[2] mpr:AB[0] -alpha Off -compose CopyOpacity -composite \) \
		mpr:AB[3] \
		mpr:AB[0] \
		miff:-; 
} |

## #Multiply diffs
## Output:
## mpr:A[0] -> colorized diff
## mpr:A[1] -> first image rasterized 
## mpr:A[2] -> diff mask
{
	convert - -write mpr:AB -delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -compose multiply -composite \) \
		mpr:AB[2] \
		mpr:AB[3] \
		miff:-; 
} | 

## #Clean the source
## Output:
## mpr:A[0] -> colorized diff
## mpr:A[1] -> first image cleaned 
{
	convert - -write mpr:AB -delete 0--1 \
		mpr:AB[0] \
		\( mpr:AB[1] mpr:AB[2] -compose plus -composite \) \
		miff:-;
} |

## #Compose the cleaned source with diff
{
	convert - -write mpr:AB -delete 0--1 \
		\( mpr:AB[1] mpr:AB[0] -composite \) \
		miff:-;
} |

display
