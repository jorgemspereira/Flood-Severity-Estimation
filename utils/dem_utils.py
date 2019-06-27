from enum import Enum

import gdal
import gdalconst
import requests


class Quadrant(Enum):
    first = 1
    second = 2
    third = 3
    fourth = 4


class Position(Enum):
    top = 1
    top_left = 2
    top_right = 3
    left = 4
    right = 5
    bottom = 6
    bottom_left = 7
    bottom_right = 8


def make_request_dsm(latitude, longitude):
    numbers_latitude = int(latitude[1:])
    letter_latitude = str(latitude[0])

    if letter_latitude == "N":
        if numbers_latitude <= 45:
            template = "https://cloud.sdsc.edu/v1/AUTH_opentopography/Raster/AW3D30/AW3D30_alos/North/North_0_45/{}"
        else:
            template = "https://cloud.sdsc.edu/v1/AUTH_opentopography/Raster/AW3D30/AW3D30_alos/North/North_46_90/{}"
    else:
        template = "https://cloud.sdsc.edu/v1/AUTH_opentopography/Raster/AW3D30/AW3D30_alos/South/{}"

    file_name = "{}{}_AVE_DSM.tif".format(latitude, longitude)
    template = template.format(file_name)
    return requests.get(template)


def read_request(request, filename):
    gdal.FileFromMemBuffer(filename, request.content)
    return gdal.Open(filename, gdalconst.GA_ReadOnly)


def get_geotiff_info(gdal_dataset):
    image = gdal_dataset.GetRasterBand(1)
    no_data_value = image.GetNoDataValue()

    cols = gdal_dataset.RasterXSize
    rows = gdal_dataset.RasterYSize

    transform = gdal_dataset.GetGeoTransform()
    x_origin, y_origin = transform[0], transform[3]
    pixel_width, pixel_height = transform[1], -transform[5]

    data = image.ReadAsArray(0, 0, cols, rows)

    return x_origin, y_origin, pixel_width, pixel_height, no_data_value, data


def find_quadrant(point, dsm_content):
    dsm_info = get_geotiff_info(dsm_content)

    if point[0] <= (dsm_info[-1].shape[0] / 2) and point[1] >= (dsm_info[-1].shape[1] / 2):
        return Quadrant.first
    if point[0] <= (dsm_info[-1].shape[0] / 2) and point[1] <= (dsm_info[-1].shape[1] / 2):
        return Quadrant.second
    if point[0] >= (dsm_info[-1].shape[0] / 2) and point[1] <= (dsm_info[-1].shape[1] / 2):
        return Quadrant.third
    if point[0] >= (dsm_info[-1].shape[0] / 2) and point[1] >= (dsm_info[-1].shape[1] / 2):
        return Quadrant.fourth


def calculate_positions_needed(point, dsm_content):
    quadrant = find_quadrant(point, dsm_content)

    if quadrant == Quadrant.first:
        return [Position.right, Position.top_right, Position.top]
    if quadrant == Quadrant.second:
        return [Position.top, Position.top_left, Position.left]
    if quadrant == Quadrant.third:
        return [Position.left, Position.bottom_left, Position.bottom]
    if quadrant == Quadrant.fourth:
        return [Position.bottom, Position.bottom_right, Position.right]


def handle_right(letter_longitude, numbers_longitude, latitude):
    if letter_longitude == "W":
        if numbers_longitude == 1:
            return latitude, "E000"
        else:
            new_number = str(numbers_longitude - 1).zfill(3)
            return latitude, "W{}".format(new_number)
    if letter_longitude == "E":
        if numbers_longitude == 180:
            raise ValueError("I dont't know...")
        else:
            new_number = str(numbers_longitude + 1).zfill(3)
            return latitude, "E{}".format(new_number)


def handle_top(letter_latitude, numbers_latitude, longitude):
    if letter_latitude == "S":
        if numbers_latitude == 1:
            return "N000", longitude
        else:
            new_number = str(numbers_latitude - 1).zfill(3)
            return "S{}".format(new_number), longitude
    if letter_latitude == "N":
        if numbers_latitude == 90:
            raise ValueError("I don't know...")
        else:
            new_number = str(numbers_latitude + 1).zfill(3)
            return "N{}".format(new_number), longitude


def handle_left(letter_longitude, numbers_longitude, latitude):
    if letter_longitude == "W":
        if numbers_longitude == 180:
            raise ValueError("I dont't know...")
        else:
            new_number = str(numbers_longitude + 1).zfill(3)
            return latitude, "W{}".format(new_number)
    if letter_longitude == "E":
        if numbers_longitude == 0:
            return latitude, "W001"
        else:
            new_number = str(numbers_longitude - 1).zfill(3)
            return latitude, "E{}".format(new_number)


def handle_bottom(letter_latitude, numbers_latitude, longitude):
    if letter_latitude == "S":
        if numbers_latitude == 90:
            raise ValueError("I dont't know...")
        else:
            new_number = str(numbers_latitude + 1).zfill(3)
            return "S{}".format(new_number), longitude
    if letter_latitude == "N":
        if numbers_latitude == 0:
            return "S001", longitude
        else:
            new_number = str(numbers_latitude - 1).zfill(3)
            return "N{}".format(new_number), longitude


def get_position_in_raster(longitude, latitude, info_raster):
    col_np = int((longitude - info_raster[0]) / info_raster[2])
    row_np = int((info_raster[1] - latitude) / info_raster[3])

    return row_np, col_np


def merge_dsm(row, dsm_content, filename):
    longitude, latitude = row['longitude'], row['latitude']
    dsm_info = get_geotiff_info(dsm_content)
    point = get_position_in_raster(longitude, latitude, dsm_info)

    longitude, latitude = row['longitude_converted'], row['latitude_converted']
    positions = calculate_positions_needed(point, dsm_content)

    numbers_longitude = int(longitude[1:])
    numbers_latitude = int(latitude[1:])

    letter_longitude = str(longitude[0])
    letter_latitude = str(latitude[0])

    to_fill = []
    for position in positions:
        if position == Position.right:
            to_fill.append(handle_right(letter_longitude, numbers_longitude, latitude))
        if position == Position.top_right:
            result_right = handle_right(letter_longitude, numbers_longitude, latitude)
            result_top = handle_top(letter_latitude, numbers_latitude, longitude)
            to_fill.append((result_top[0], result_right[1]))
        if position == Position.top:
            to_fill.append(handle_top(letter_latitude, numbers_latitude, longitude))
        if position == Position.top_left:
            result_left = handle_left(letter_longitude, numbers_longitude, latitude)
            result_top = handle_top(letter_latitude, numbers_latitude, longitude)
            to_fill.append((result_top[0], result_left[1]))
        if position == Position.left:
            to_fill.append(handle_left(letter_longitude, numbers_longitude, latitude))
        if position == Position.bottom_left:
            result_left = handle_left(letter_longitude, numbers_longitude, latitude)
            result_bottom = handle_bottom(letter_latitude, numbers_latitude, longitude)
            to_fill.append((result_bottom[0], result_left[1]))
        if position == Position.bottom:
            to_fill.append(handle_bottom(letter_latitude, numbers_latitude, longitude))
        if position == Position.bottom_right:
            result_right = handle_right(letter_longitude, numbers_longitude, latitude)
            result_bottom = handle_bottom(letter_latitude, numbers_latitude, longitude)
            to_fill.append((result_bottom[0], result_right[1]))

    names = []
    for index, item in enumerate(to_fill):
        try:
            name = "/vsimem/dsm{}".format(index)
            read_request(make_request_dsm(item[0], item[1]), name)
            names.append(name)
        except RuntimeError:
            pass

    content = gdal.BuildVRT("/vsimem/vrt", names + ["/vsimem/dsm"], VRTNodata=-9999)
    final_content = gdal.Translate(filename, content)

    for name in names:
        gdal.Unlink(name)

    return final_content


def fill_no_data(dsm_content, filename):
    file_srtm = gdal.Open("./dems/srtm30_merged.tif")
    interpolated = interpolate(file_srtm, dsm_content, "/vsimem/lowest_res")
    file_eu_dem = gdal.Open("./dems/eu_dem.tif")
    interpolated_eu_dem = interpolate(file_eu_dem, dsm_content, "/vsimem/eu_dem")
    content = gdal.Warp(filename, [interpolated, interpolated_eu_dem, dsm_content])
    gdal.Unlink("/vsimem/lowest_res")
    gdal.Unlink("/vsimem/eu_dem")
    return content


def interpolate(src_content, reference_content, output_filename):
    src_proj = src_content.GetProjection()

    reference_proj = reference_content.GetProjection()
    reference_trans = reference_content.GetGeoTransform()
    x = reference_content.RasterXSize
    y = reference_content.RasterYSize

    driver = gdal.GetDriverByName('GTiff')
    output = driver.Create(output_filename, x, y, 1, gdalconst.GDT_Float32)
    band = output.GetRasterBand(1)
    band.SetNoDataValue(-9999)
    band.Fill(-9999, 0.0)
    output.SetGeoTransform(reference_trans)
    output.SetProjection(reference_proj)
    gdal.ReprojectImage(src_content, output, src_proj, reference_proj, gdalconst.GRA_CubicSpline)

    return output
