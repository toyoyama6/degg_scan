import cv2
import os
import numpy as np

from termcolor import colored
import click
from glob import glob

H_size = 1312
V_size = 979

def Raw2Gray(img):
    npy = np.fromfile(img, dtype=np.uint16, count=H_size*V_size)
    npy = np.reshape(npy, (V_size, H_size), 'C')
    npy = cv2.cvtColor(npy, cv2.COLOR_BAYER_BG2BGR)
    npy = (npy/256).astype('uint8')
    return npy

def Find_Pattern(img, outfile):

    #This function detects the pattern in theimage using openCVs SimpleBlobDetector
    params = cv2.SimpleBlobDetector_Params()

    params.thresholdStep = 1
    params.minThreshold = 25
    params.maxThreshold = 250
    #Set area filter parameters. This excludes areas that are too small
    params.filterByArea = True
    params.minArea = 100
    #Set Circularity filter parameters. This makes sure that no shapes are included that are extremely distorted
    params.filterByCircularity = True
    params.minCircularity = 0.4
    # Set Convexity filtering parameters. This excludes shapes that have convex edges
    params.filterByConvexity = True
    params.minConvexity = 0.2
    # Set inertia filtering parameters
    params.filterByInertia = True
    params.minInertiaRatio = 0.01
    # Create a detector with the parameters
    detector = cv2.SimpleBlobDetector_create(params)
    # Detect blobs
    keypoints = detector.detect(img)

    im_with_keypoints = cv2.drawKeypoints(img, keypoints, np.array([]), (0,0,255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

    #cv2.imshow('with keypoints',im_with_keypoints)
    cv2.imwrite(f'{outfile}.png', im_with_keypoints)

    #print('The number of blobs is ' + str(len(keypoints)))

    #for x in keypoints:

        #print('The size of this blob is ' + str(x.size))

        #if x.size > 10:

            #if a large enough ellipse is found pass the test
            #return(True)

    if (len(keypoints) > 9) and (cv2.Laplacian(img, cv2.CV_64F).var() >4.0):
        return True
    else:
        return False

@click.command()
@click.argument('image_folder')
def main(image_folder):
        glob_path = os.path.join(image_folder,'*.RAW' )
        images = glob(glob_path)
        for i, _image in enumerate(images):
            print(f'File Path: {_image}')
            if os.path.getsize(_image) == 2605632:
                        image = Raw2Gray(_image)
                        print(f'Variance of laplacian is: {str(cv2.Laplacian(image, cv2.CV_64F).var())}')
                        verdict = Find_Pattern(image, i)
                        if verdict == True:
                            print(colored('Pass', 'green'))
                        if verdict == False:
                            print(colored('Fail', 'red'))

if __name__ == "__main__":
    main()
##end
