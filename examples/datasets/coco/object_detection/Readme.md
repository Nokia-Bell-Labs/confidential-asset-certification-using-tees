Contributed by: Istemi Ekin Akkus

Integrated and tested by: Istemi Ekin Akkus

This folder contains the property computation code for detecting objects in [COCO dataset](https://cocodataset.org).

The code uses [YOLOv3](https://pjreddie.com/darknet/yolo/) object detection model.

The model weights are available through a [third-party](https://github.com/patrick013/Object-Detection---Yolov3/raw/refs/heads/master/model/yolov3.weights)
because they are not available anymore through the above official channel.

The code uses the model to detect various objects in the images, keeps track of how many objects were detected in the entire dataset and produces statistics about their counts.

It currently uses the [2017 Val Images](https://cocodataset.org/#download). Modify the `config.json` file to change the dataset.
