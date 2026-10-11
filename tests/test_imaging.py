import io

from PIL import Image

from framestar.imaging import fill_frame


def test_fill_frame_letterboxes_portrait_onto_backdrop():
    src = io.BytesIO()
    Image.new("RGB", (600, 900), (250, 20, 20)).save(src, "JPEG")
    framed = Image.open(io.BytesIO(fill_frame(src.getvalue())))
    assert framed.size == (1280, 800)
    center = framed.getpixel((640, 400))
    edge = framed.getpixel((5, 400))
    assert center[0] > 200
    assert 0 < edge[0] < 150
