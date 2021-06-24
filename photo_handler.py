import math, string, os

import pytesseract
from cv2 import cv2
import numpy as np

import settings

pytesseract.pytesseract.tesseract_cmd = settings.TERSSERACT_PATH


def save_photo(photo_obj, bot):
    photo = bot.download_file(photo_obj.file_path)
    photo_path = settings.PHOTO_DIR_PATH + photo_obj.file_path[photo_obj.file_path.index('/') + 1:]
    with open(photo_path, 'wb') as photo_file:
        photo_file.write(photo)
    img = cv2.imread(photo_path)
    new_photo_path = photo_path[:photo_path.index('.')] + '.png'
    cv2.imwrite(new_photo_path, img)
    os.remove(photo_path)
    return new_photo_path


def show(img):
    scale_percent = 80  # Процент от изначального размера
    width = int(img.shape[1] * scale_percent / 100)
    height = int(img.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
    cv2.imshow("", resized)
    cv2.waitKey(0)


def get_number_by_path(img_path):
    img = cv2.imread(img_path)
    return get_number(img)


def get_number(img):
    try:
        thresh = threshhold_high(img)
        text = pytesseract.image_to_string(thresh, lang='ukr')
        number = number_from_text(text)
        if number:
            return number

        img = to_vertical(img)
        img = threshhold_high(img)

        text = pytesseract.image_to_string(img, lang='ukr')
        number = number_from_text(text)
        return number
    except Exception:
        return None


def number_from_text(text):
    words = text.split()

    for word in words:
        word = word.strip(string.punctuation)
        if is_number(word) and len(word) >= 5:
            return int(word)

    return None


def is_number(s):
    try:
        s = int(s)
    except Exception:
        return False
    else:
        return True


def threshhold_low(img):
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31,
                                3)  # 31 3 - good coeffs
    return img


def threshhold_high(img):
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 121,
                                35)  # 121 35 - good coeffs
    return img


def to_vertical(img):
    old_img = img.copy()
    img = threshhold_low(img)
    img = cv2.bitwise_not(img)

    lines = cv2.HoughLinesP(img, 1, np.pi / 180, 40, minLineLength=400, maxLineGap=10)
    if lines is None:
        return old_img
    phi = 0

    (h, w) = img.shape[:2]
    center = (w / 2, h / 2)

    for x1, y1, x2, y2 in lines[0]:
        # cv2.line(result, (x1, y1), (x2, y2), (255, 0, 0), 3)
        phi = math.atan((x2 - x1) / (y1 - y2)) * (180 / math.pi)

    rotation_matrix = cv2.getRotationMatrix2D(center, phi, 1.0)
    rotated = cv2.warpAffine(old_img, rotation_matrix, (w, h))

    return rotated


if __name__ == "__main__":
    img_ = cv2.imread('7.jpg')
    show(img_)
    thresh = threshhold_low(img_)
    show(thresh)
    img_ = to_vertical(img_)
    show(img_)
    img_ = threshhold_high(img_)
    show(img_)

    print(pytesseract.image_to_string(img_, lang = "ukr"))
