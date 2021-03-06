import json
import logging
import os
import subprocess

import cv2

# for tests
try:
    import utils.fix_frame as fix_frame
    import utils.kino_exceptions as kino_exceptions
    import utils.palette as palette
except ImportError:
    import palette
    import fix_frame

import re

from PIL import Image, ImageChops, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff)  # , 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)


def cleansub(text):
    cleanr = re.compile("<.*?>")
    cleantext = re.sub(cleanr, "", text)
    return cleantext.replace("♪", "")


def convert2Pil(c2vI):
    image = cv2.cvtColor(c2vI, cv2.COLOR_BGR2RGB)
    return Image.fromarray(image)


def get_gif(file, second, microsecond=0, isgif=True):
    " gifs deprecated "
    logger.info("Extracting frame")
    capture = cv2.VideoCapture(file)
    fps = capture.get(cv2.CAP_PROP_FPS)
    logger.info("FPS: {}".format(fps))
    extra_frames = int(25 * (microsecond * 0.000001)) if microsecond else 0
    logger.info("Calculated extra frames: {}".format(extra_frames))
    frame_start = int(fps * second) + extra_frames
    pils = []
    if isgif:
        frame_stop = int(fps * 3) + frame_start

        cv2s = []
        for i in range(frame_start, frame_stop, 3):
            capture.set(1, i)
            ret, frame = capture.read()
            cv2s.append(frame)
        height, width, lay = cv2s[0].shape

        for i in cv2s:
            pils.append(convert2Pil(i))
        return
    else:
        capture.set(1, frame_start)
        ret, frame = capture.read()
        return frame


def check_offensive_content(title):
    with open(os.environ.get("OFFENSIVE_WORDS")) as w:
        for i in json.load(w):
            if i in title.lower():
                raise kino_exceptions.OffensiveWord


def extract_frame_ffmpeg(file, sec):
    logger.info("cv2 failed. Falling back to ffmpeg")
    tmp_image = "/tmp/tmp_pil.png"
    command = [
        "ffmpeg",
        "-ss",
        str(sec),
        "-copyts",
        "-i",
        file,
        "-vf",
        "scale=iw*sar:ih",
        "-vframes",
        "1",
        tmp_image,
    ]
    subprocess.run(command, stdout=subprocess.PIPE)
    new_image = cv2.imread(tmp_image)
    os.remove(tmp_image)
    return new_image


# draw subtitles to frame
def get_subtitles(img, title):
    check_offensive_content(title)
    title = cleansub(title)
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = ImageFont.truetype("helvetica.ttf", int(h * 0.055))
    off = w * 0.067
    txt_w, txt_h = draw.textsize(title, font)
    draw.text(
        ((w - txt_w) / 2, h - txt_h - off),
        title,
        "white",
        font=font,
        align="center",
        stroke_width=4,
        stroke_fill="black",
    )
    return img


def sub_iterator(pils, content, sub_start, sub_end):
    lenght = len(pils) / 3
    sub_range = int((sub_end - sub_start) * lenght)
    new_pils = []
    try:
        for i in range(sub_range):
            new_pils.append(get_subtitles(pils[i], content["message"]))
        for d in range(sub_range, len(pils)):
            new_pils.append(pils[d])
    except IndexError:
        pass
    return new_pils


def main(file, source=None, second=None, subtitle=None, gif=False, multiple=False):
    if gif:
        if subtitle and not second:
            pils = get_gif(file, subtitle["start"])
            new_pils = sub_iterator(pils, subtitle, subtitle["start"], subtitle["end"])
        else:
            new_pils = get_gif(file, int(second))
    else:
        dotrim = False
        try:
            dotrim = True if "web" in source.lower() else False
        except Exception as e:
            logger.error(e, exc_info=True)
        if subtitle:
            cv2_obj = get_gif(file, subtitle["start"], subtitle["start_m"], isgif=False)
            new_pil, palette_needed = fix_frame.needed_fixes(file, cv2_obj)
            the_pil = get_subtitles(new_pil, subtitle["message"])
        else:
            cv2_obj = get_gif(file, int(second), microsecond=0, isgif=False)
            the_pil, palette_needed = fix_frame.needed_fixes(file, cv2_obj)
    if multiple:
        return the_pil
    if palette_needed:
        return palette.getPalette(the_pil)
    else:
        return the_pil
    # use imageio if list
    # imageio.mimsave('whatever.gif', list)
