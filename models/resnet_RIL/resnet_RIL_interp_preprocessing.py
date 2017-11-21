""" PRE-PROCESSING FILE FOR IMAGES IN THE VGG NETWORK, TAKEN FROM TF SLIM SOURCE CODE:
https://github.com/tensorflow/models/blob/master/slim/preprocessing/vgg_preprocessing.py  """
import numpy as np
import cv2

_R_MEAN = 123.68
_G_MEAN = 116.78
_B_MEAN = 103.94

_RESIZE_SIDE_MIN = 256
_RESIZE_SIDE_MAX = 512

def _crop(image, offset_height, offset_width, crop_height, crop_width):
    """
    Crops the given image using the provided offsets and sizes.
    Note that the method doesn't assume we know the input image size but it does
    assume we know the input image rank.
    Args:
        :image:         an image of shape [height, width, channels].
        :offset_height: a scalar tensor indicating the height offset.
        :offset_width:  a scalar tensor indicating the width offset.
        :crop_height:   the height of the cropped image.
        :crop_width:    the width of the cropped image.

    Returns:
        the cropped (and resized) image.
    Raises:
        InvalidArgumentError: if the rank is not 3 or if the image dimensions are
        less than the crop size.
  """

    original_shape = image.shape
    offset_height  = int(offset_height)
    offset_width   = int(offset_width)
    crop_height    = int(crop_height)
    crop_width     = int(crop_width)
    
    image = image[offset_height:offset_height+crop_height, offset_width:offset_width+crop_width,:]
    
    return image.reshape((crop_height, crop_width, original_shape[2]))


def _random_crop(image_list, crop_height, crop_width):
    """
    Crops the given list of images.
    The function applies the same crop to each image in the list. This can be
    effectively applied when there are multiple image inputs of the same
    dimension such as:
    image, depths, normals = _random_crop([image, depths, normals], 120, 150)
    Args:
        :image_list:  a list of image tensors of the same dimension but possibly
                      varying channel.
        :crop_height: the new height.
        :crop_width:  the new width.

    Returns:
        the image_list with cropped images.
    Raises:
        ValueError: if there are multiple image inputs provided with different size
        or the images are smaller than the crop dimensions.
  """

    image_shape  = image_list[0].shape
    image_height = image_shape[0]
    image_width  = image_shape[1]
    
    # Create a random bounding box.
    max_offset_height = image_height - crop_height + 1
    max_offset_width  = image_width - crop_width + 1
    
    offset_height = np.random.uniform(high=max_offset_height)
    offset_width  = np.random.uniform(high=max_offset_width)
    
    return [_crop(image, offset_height, offset_width,
                  crop_height, crop_width) for image in image_list]


def _central_crop(image_list, crop_height, crop_width):
    """
    Performs central crops of the given image list.
    Args:
        :image_list:  a list of image tensors of the same dimension but possibly
                      varying channel.
        :crop_height: the height of the image following the crop.
        :crop_width:  the width of the image following the crop.

    Returns:
        the list of cropped images.
    """

    outputs = []
    
    for image in image_list:
        image_height = image.shape[0]
        image_width  = image.shape[1]
        
        offset_height = (image_height - crop_height) / 2
        offset_width  = (image_width - crop_width) / 2
        
        outputs.append(_crop(image, offset_height, offset_width,
                             crop_height, crop_width))
    
    # END FOR

    return outputs


def _mean_image_subtraction(image, means):
    """
    Subtracts the given means from each image channel.
    For example:
        means = [123.68, 116.779, 103.939]
        image = _mean_image_subtraction(image, means)
    Note that the rank of `image` must be known.
    Args:
        :image: a tensor of size [height, width, C].
        :means: a C-vector of values to subtract from each channel.

    Returns:
        the centered image.
    Raises:
        ValueError: If the rank of `image` is unknown, if `image` has a rank other
        than three or if the number of channels in `image` doesn't match the
        number of values in `means`.
    """

    num_channels = image.shape[-1]
    
    for i in range(num_channels):
      image[:,:,i] -= means[i]

    # END FOR
    
    return image


def _smallest_size_at_least(height, width, smallest_side):
    """
    Computes new shape with the smallest side equal to `smallest_side`.
    Computes new shape with the smallest side equal to `smallest_side` while
    preserving the original aspect ratio.
    Args:
        :height:        an int32 scalar tensor indicating the current height.
        :width:         an int32 scalar tensor indicating the current width.
        :smallest_side: A python integer or scalar `Tensor` indicating the size of
                        the smallest side after resize.
    Returns:
        :new_height: an int32 scalar tensor indicating the new height.
        :new_width: and int32 scalar tensor indicating the new width.
    """

    scale = (smallest_side/width) if (height > width) else (smallest_side/height)
    
    return int(height*scale),int(width*scale)


def _aspect_preserving_resize(image, smallest_side):
    """
    Resize images preserving the original aspect ratio.
    Args:
        :image:         A 3-D image `Tensor`.
        :smallest_side: A python integer or scalar `Tensor` indicating the size of
                        the smallest side after resize.
    Returns:
        :resized_image: A 3-D tensor containing the resized image.
  """

    shape  = image.shape
    height = shape[0]
    width  = shape[1]
    
    new_height, new_width = _smallest_size_at_least(float(height), float(width), float(smallest_side))
    
    resized_image = cv2.resize(image, (new_height, new_width))
    
    return resized_image


def preprocess_for_train(image,
                         output_height,
                         output_width,
                         resize_side_min=_RESIZE_SIDE_MIN,
                         resize_side_max=_RESIZE_SIDE_MAX):
    """
    Preprocesses the given image for training.
    Note that the actual resizing scale is sampled from
    [`resize_size_min`, `resize_size_max`].
    Args:
        :image:           A `Tensor` representing an image of arbitrary size.
        :output_height:   The height of the image after preprocessing.
        :output_width:    The width of the image after preprocessing.
        :resize_side_min: The lower bound for the smallest side of the image for
                          aspect-preserving resizing.
        :resize_side_max: The upper bound for the smallest side of the image for
                          aspect-preserving resizing.

    Returns:
        A preprocessed image.
    """

    image = _aspect_preserving_resize(image, resize_side_min)
    image = _random_crop([image], output_height, output_width)[0]
    image = image.reshape((output_height, output_width,3))
    image = image.astype('float32')
    
    if np.random.randint(low=0, high=1, size=1) > 0:
      image = image[:,::-1,:]

    # END IF

    return _mean_image_subtraction(image, [_R_MEAN, _G_MEAN, _B_MEAN])


def _preprocess_for_eval(image, output_height, output_width, resize_side):
    """
    Preprocesses the given image for evaluation.
    Args:
        :image:         A `Tensor` representing an image of arbitrary size.
        :output_height: The height of the image after preprocessing.
        :output_width:  The width of the image after preprocessing.
        :resize_side:   The smallest side of the image for aspect-preserving resizing.

    Returns:
        A preprocessed image.
    """
    image = _aspect_preserving_resize(image, resize_side)
    image = _central_crop([image], output_height, output_width)[0]
    image = image.reshape((output_height, output_width, 3))
    image = image.astype('float32')

    return _mean_image_subtraction(image, [_R_MEAN, _G_MEAN, _B_MEAN])


def preprocess_image(image, output_height, output_width, is_training=False,
                     resize_side_min=_RESIZE_SIDE_MIN,
                     resize_side_max=_RESIZE_SIDE_MAX):
    """Preprocesses the given image.
    Args:
      image: A `Tensor` representing an image of arbitrary size.
      output_height: The height of the image after preprocessing.
      output_width: The width of the image after preprocessing.
      is_training: `True` if we're preprocessing the image for training and
        `False` otherwise.
      resize_side_min: The lower bound for the smallest side of the image for
        aspect-preserving resizing. If `is_training` is `False`, then this value
        is used for rescaling.
      resize_side_max: The upper bound for the smallest side of the image for
        aspect-preserving resizing. If `is_training` is `False`, this value is
        ignored. Otherwise, the resize side is sampled from
          [resize_size_min, resize_size_max].
    Returns:
      A preprocessed image.
    """
    if is_training:
        return preprocess_for_train(image, output_height, output_width,
                                    resize_side_min, resize_side_max)
    else:
        return _preprocess_for_eval_new(image, output_height, output_width,
                                        resize_side_min)

def _window_function(Data, Type, k):
    """
    :type  Data: numpy array (4D)
    :param Data: Multi-frame input

    :type  Type: string
    :param Type: Type of video input (All frames, Sliding window: Kframes and
                 Sliding window with overlap: Kframes at K/2 overlap)

    :type  k: int
    :param k: Integer number denoting sliding window size

    """
    # K frame sliding window without any overlap
    if Type == 'kframes' or Type == 'kframespad':

        Data  = Data[:(Data.shape[0]/k) * k, :, :, :]

    # END IF

    return Data

def preprocess(index, data, labels, size, is_training):
    """
    Args:
        :index:       Integer used to index a video from a given text file listing all available videos
        :data:        Original data
        :label:       True labels   
        :size:        List detailing final height and width from preprocessing  
        :is_training: Boolean value indicating phase (TRAIN or TEST)

    Return:
        :vid_clips:  Preprocessed video clips
    """

    # Seeded offset for every video
    np.random.seed(index)

    temp_offset = np.random.randint(0, data.shape[0]-1, 1)

    tfootprint = 250

    # Check if total index number is > size of data
    if temp_offset + tfootprint > data.shape[0]-1:
        # Check if looping over can be done in a single shot
        if temp_offset + tfootprint - data.shape[0]-1 < data.shape[0]-1:
            data = np.vstack((data[temp_offset[0]:,:,:,:],data[:temp_offset[0]+tfootprint - data.shape[0],:,:,:]))

        else:
            temp_data = data[temp_offset[0]:,:,:,:]

            while(temp_data.shape[0]<tfootprint):
                if data.shape[0] <= tfootprint - temp_data.shape[0]:
                    temp_data = np.vstack((temp_data, data))

                else:
                    temp_data = np.vstack((temp_data, data[:tfootprint - temp_data.shape[0],:,:,:]))

                # END IF

            # END WHILE

            data = temp_data
            del temp_data

        # END IF

    else:
        data = data[temp_offset[0]:temp_offset[0]+tfootprint,:,:,:]

    # END IF

    temp_data = []
    data      = data.astype('float32')

    for im in data:
        temp_data.append(_preprocess_for_eval(im, size[1], size[0], min(size)))

    # END FOR

    data = np.array(temp_data)

    return data