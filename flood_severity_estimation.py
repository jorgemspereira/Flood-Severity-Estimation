import datetime
import json
import sys
from enum import Enum
from pathlib import Path

import gdal
import math
import numpy as np
import pandas as pd
import requests
from gdal import gdalconst
from tqdm import tqdm


SLOPE_THRESHOLD = 90

water_one_day = "http://www.gdacs.org/flooddetection/DATA/ALL/SignalTiffs/{}/{}/signal_{}{}{}_ALL.tif"
water_avg_days = "http://www.gdacs.org/flooddetection/DATA/ALL/AvgSignalTiffs/{}/{}/signal_4days_avg_4days_{}{}{}.tif"

magnitude_one_day = "http://www.gdacs.org/flooddetection/DATA/ALL/MagTiffs/{}/{}/mag_signal_{}{}{}_ALL.tif"
magnitude_avg_days = "http://www.gdacs.org/flooddetection/DATA/ALL/AvgMagTiffs/{}/" \
                     "{}/mag_4days_signal_4days_avg_4days_{}{}{}.tif"

epsg_54009 = 'PROJCS["World_Mollweide",' \
                'GEOGCS["GCS_WGS_1984",' \
                    'DATUM["D_WGS_1984",' \
                    'SPHEROID["WGS_1984",6378137,298.257223563]],' \
                    'PRIMEM["Greenwich",0],' \
                    'UNIT["Degree",0.017453292519943295]],' \
             'PROJECTION["Mollweide"],' \
             'PARAMETER["False_Easting",0],' \
             'PARAMETER["False_Northing",0],' \
             'PARAMETER["Central_Meridian",0],' \
             'UNIT["Meter",1]]'


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


def make_request_floods(day, month, year, template):
    url = template.format(year, str(month).zfill(2), year, str(month).zfill(2), str(day).zfill(2))
    return requests.get(url)


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


def read_dataset_and_metadata(dataset_path, metadata_path):
    all_df = pd.read_csv(dataset_path, names=['filename', 'class'])
    flooded_df = all_df.drop(all_df[all_df['class'] != 1].index).reset_index(drop=True)
    flooded_df = flooded_df.drop(['class'], axis=1).reset_index(drop=True)

    flooded_df['year'], flooded_df['month'], flooded_df['day'] = None, None, None
    flooded_df['latitude_converted'], flooded_df['longitude_converted'] = None, None
    flooded_df['latitude'], flooded_df['longitude'] = None, None

    with open(metadata_path, encoding="utf-8") as f:
        data = json.load(f, encoding='utf-8')

    return flooded_df, data


def get_flooded_mediaeval_info(classification_path, metadata_path):
    flooded_df, metadata = read_dataset_and_metadata(classification_path, metadata_path)

    for index, row in flooded_df.iterrows():
        try:
            image_entry = [obj for obj in metadata['images'] if obj['image_id'] == str(row['filename'])][0]

            date_taken = image_entry['date_taken'].split(".")[0]
            date_taken = datetime.datetime.strptime(date_taken, '%Y-%m-%d %H:%M:%S').timetuple()

            row['year'] = date_taken.tm_year
            row['month'] = date_taken.tm_mon
            row['day'] = date_taken.tm_mday

            row['longitude'] = image_entry['longitude']
            row['latitude'] = image_entry['latitude']

            longitude_converted, latitude_converted = round_coordinates(row['longitude'], row['latitude'])
            row['longitude_converted'] = longitude_converted
            row['latitude_converted'] = latitude_converted

            flooded_df.iloc[index] = row
        except TypeError:
            pass

    return flooded_df.dropna().reset_index(drop=True)


def get_flooded_europeanfloods_info():
    classification_path = "./datasets/european_floods_2013_gt.csv"
    metadata_path = "./datasets/european_floods_2013_metadata.json"
    flooded_df, metadata = read_dataset_and_metadata(classification_path, metadata_path)

    for index, row in flooded_df.iterrows():
        try:
            image_entry = [obj for obj in metadata if str(obj['pageid']) == str(row['filename'])][0]

            date_taken = image_entry['capture_time']
            date_taken = datetime.datetime.strptime(date_taken, '%Y-%m-%dT%H:%M:%S').timetuple()

            row['year'] = date_taken.tm_year
            row['month'] = date_taken.tm_mon
            row['day'] = date_taken.tm_mday

            row['longitude'] = image_entry['coordinates']['lon']
            row['latitude'] = image_entry['coordinates']['lat']

            longitude_converted, latitude_converted = round_coordinates(row['longitude'], row['latitude'])
            row['longitude_converted'] = longitude_converted
            row['latitude_converted'] = latitude_converted

            flooded_df.iloc[index] = row
        except (KeyError, IndexError, TypeError):
            pass

    return flooded_df.dropna().reset_index(drop=True)


def dd2dms(longitude, latitude):
    split_degx = math.modf(longitude)
    degrees_x = int(split_degx[1])
    minutes_x = abs(int(math.modf(split_degx[0] * 60)[1]))
    seconds_x = abs(round(math.modf(split_degx[0] * 60)[0] * 60, 2))

    split_degy = math.modf(latitude)
    degrees_y = int(split_degy[1])
    minutes_y = abs(int(math.modf(split_degy[0] * 60)[1]))
    seconds_y = abs(round(math.modf(split_degy[0] * 60)[0] * 60, 2))

    eorw = "W" if degrees_x < 0 else "E"
    nors = "S" if degrees_y < 0 else "N"

    x = [abs(degrees_x), minutes_x, seconds_x, eorw]
    y = [abs(degrees_y), minutes_y, seconds_y, nors]

    return x, y


def round_coordinates(longitude, latitude):
    longitude_converted, latitude_converted = dd2dms(longitude, latitude)
    longitude_letter, latitude_letter = longitude_converted[-1], latitude_converted[-1]

    longitude = longitude_converted[0]
    latitude = latitude_converted[0]

    longitude = longitude + 1 if "W" == longitude_letter else longitude
    latitude = latitude if "N" == latitude_letter else latitude + 1

    longitude = "{}{}".format(longitude_letter, str(int(longitude)).zfill(3))
    latitude = "{}{}".format(latitude_letter, str(int(latitude)).zfill(3))

    return longitude, latitude


def interpolate(src_content, reference_content, output_filename):
    src_proj = src_content.GetProjection()

    reference_proj = reference_content.GetProjection()
    reference_trans = reference_content.GetGeoTransform()
    x = reference_content.RasterXSize
    y = reference_content.RasterYSize

    driver = gdal.GetDriverByName('GTiff')
    output = driver.Create(output_filename, x, y, 1, gdalconst.GDT_Float32)
    output.SetGeoTransform(reference_trans)
    output.SetProjection(reference_proj)
    gdal.ReprojectImage(src_content, output, src_proj, reference_proj, gdalconst.GRA_Bilinear)

    return output


def get_position_in_raster(longitude, latitude, info_raster):
    col_np = int((longitude - info_raster[0]) / info_raster[2])
    row_np = int((info_raster[1] - latitude) / info_raster[3])

    return row_np, col_np


def get_average_elevation(position, info, slope_info):
    row, col = position[0], position[1]

    positions = [(row - 1, col - 1), (row - 1, col - 0), (row - 1, col + 1),
                 (row + 0, col - 1), (row + 0, col + 1),
                 (row + 1, col - 1), (row + 1, col - 0), (row + 1, col + 1)]

    to_delete = []
    for pos in positions:
        if slope_info[-1][pos[0]][pos[1]] > SLOPE_THRESHOLD:
            to_delete.append(pos)

    for pos in to_delete:
        positions.remove(pos)

    # Add the center to calculate average
    positions.append((row, col))

    result = []
    for pos in positions:
        result.append(info[-1][pos[0]][pos[1]])

    return np.mean(result)


def get_maximum_elevation(positions, info, slope_info):
    maximum_elevation = -sys.maxsize - 1
    for position in positions:
        current_elevation = info[-1][position[0]][position[1]]
        if current_elevation > maximum_elevation and slope_info[-1][position[0]][position[1]] < SLOPE_THRESHOLD:
            maximum_elevation = current_elevation
    return maximum_elevation


def get_neighbors_position(init_position, current_position, neighborhood=50):
    row, col = current_position[0], current_position[1]
    positions = [(row - 1, col - 1), (row - 1, col - 0), (row - 1, col + 1),
                 (row + 0, col - 1), (row + 0, col + 1),
                 (row + 1, col - 1), (row + 1, col - 0), (row + 1, col + 1)]

    to_delete = []
    for pos in positions:
        if abs(pos[0] - init_position[0]) > neighborhood or abs(pos[1] - init_position[1]) > neighborhood:
            to_delete.append(pos)

    for pos in to_delete:
        positions.remove(pos)

    return positions


def get_neighbors_info(neighbors, info):
    if info is None:
        return None

    lbs = []
    for neighbor in neighbors:
        lbs.append(info[-1][neighbor[0]][neighbor[1]])
    return lbs


def get_label_for_point(position, info):
    row, col = position[0], position[1]
    return info[-1][row][col]


def get_label_for_neighbor(info_interpolated, info_one, info_avg, neighbor_index):
    if info_interpolated is None:
        return info_avg[neighbor_index]

    if info_one[neighbor_index] == info_interpolated[-2]:
        return info_avg[neighbor_index]

    return info_one[neighbor_index]


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

    gdal.Unlink("/vsimem/vrt")

    return final_content


def get_flood_information(day, month, year, template, dsm_content):

    try:
        content = read_request(make_request_floods(day, month, year, template), "/vsimem/temp")
    except RuntimeError:
        # Information for that day may not exist
        return None

    content_interpolated = get_geotiff_info(interpolate(content, dsm_content, "/vsimem/temp_inter"))
    gdal.Unlink("/vsimem/temp_inter")
    gdal.Unlink("/vsimem/temp")
    return content_interpolated


def fill_no_data(dsm_content, filename):
    file_srtm = gdal.Open("./srtm30_merged/srtm30_merged.tif")
    interpolated = interpolate(file_srtm, dsm_content, "/vsimem/lowest_res")
    content = gdal.Warp(filename, [interpolated, dsm_content])
    gdal.Unlink("/vsimem/lowest_res")
    return content


def calculate_slope(dsm_content, filename):
    ds = gdal.Warp("/vsimem/mod", dsm_content, dstSRS=epsg_54009)
    content = gdal.DEMProcessing("/vsimem/tmp", ds, 'slope', options=gdal.DEMProcessingOptions(slopeFormat="percent"))
    output = interpolate(content, dsm_content, filename)
    gdal.Unlink("/vsimem/mod")
    gdal.Unlink("/vsimem/tmp")
    return output


def region_flooding_algorithm(row):
    longitude, latitude = row['longitude'], row['latitude']
    day, month, year = row['day'], row['month'], row['year']
    longitude_converted, latitude_converted = row['longitude_converted'], row['latitude_converted']

    try:
        dsm_content = read_request(make_request_dsm(latitude_converted, longitude_converted), "/vsimem/dsm")
        dsm_content = merge_dsm(row, dsm_content, "/vsimem/dsm_merged")
        dsm_content = fill_no_data(dsm_content, "/vsimem/dsm_final")
    except RuntimeError as e:
        print(e)
        return 0.0

    slope_info = get_geotiff_info(calculate_slope(dsm_content, "/vsimem/slope"))
    gdal.Unlink("/vsimem/slope")

    water_one_interpolated = get_flood_information(day, month, year, water_one_day, dsm_content)
    water_avg_interpolated = get_flood_information(day, month, year, water_avg_days, dsm_content)

    mag_one_interpolated = get_flood_information(day, month, year, magnitude_one_day, dsm_content)
    mag_avg_interpolated = get_flood_information(day, month, year, magnitude_avg_days, dsm_content)

    dsm_info = get_geotiff_info(dsm_content)
    init_position = get_position_in_raster(longitude, latitude, dsm_info)
    original_elevation = get_label_for_point(init_position, dsm_info)
    gdal.Unlink("/vsimem/dsm_final")

    already_visited = []
    to_process_lst = [init_position]

    while len(to_process_lst) != 0:
        current_position = to_process_lst.pop()
        already_visited.append(current_position)

        neighbors_position = get_neighbors_position(init_position, current_position)
        elevation_neighbors_info = get_neighbors_info(neighbors_position, dsm_info)
        water_one_neighbors_info = get_neighbors_info(neighbors_position, water_one_interpolated)
        water_avg_neighbors_info = get_neighbors_info(neighbors_position, water_avg_interpolated)
        magnitude_one_neighbors_info = get_neighbors_info(neighbors_position, mag_one_interpolated)
        magnitude_avg_neighbors_info = get_neighbors_info(neighbors_position, mag_avg_interpolated)

        for neighbor_index in range(len(neighbors_position)):
            neighbor_position = neighbors_position[neighbor_index]
            if neighbor_position in already_visited or neighbor_position in to_process_lst:
                continue

            elevation_label = elevation_neighbors_info[neighbor_index]
            if elevation_label == dsm_info[-2]:
                continue

            water_label = get_label_for_neighbor(water_one_interpolated, water_one_neighbors_info,
                                                 water_avg_neighbors_info, neighbor_index)
            magnitude_label = get_label_for_neighbor(mag_one_interpolated, magnitude_one_neighbors_info,
                                                     magnitude_avg_neighbors_info, neighbor_index)

            if water_label is not None and magnitude_label is not None:
                water_label = water_label / 1000000
                magnitude_label = magnitude_label / 1000

                if (water_label < 0.5 or magnitude_label > 2) and elevation_label < original_elevation:
                    to_process_lst.append(neighbor_position)

    avg_elevation = get_average_elevation(init_position, dsm_info, slope_info)
    maximum_elevation = get_maximum_elevation(already_visited, dsm_info, slope_info)
    return abs(maximum_elevation - avg_elevation)


def verify_pixels(df, output_name):
    if Path(output_name).is_file():
        result_df = pd.read_csv(output_name, names=['filename', 'height'])
    else:
        result_df = pd.DataFrame(columns=['filename', 'height'])

    progress_bar = tqdm(total=df.shape[0])
    for index, row in df.iterrows():
        if str(row['filename']) not in result_df['filename'].values.astype(str):
            result = {}
            water_level = region_flooding_algorithm(row)
            result['filename'] = row['filename']
            result['height'] = '%.2f' % round(water_level, 2)
            result_df.loc[len(result_df)] = result
            result_df.to_csv(output_name, header=False, index=False)
        progress_bar.update(1)


def main():
    mediaeval_test_df = get_flooded_mediaeval_info("./datasets/mediaeval2017_testset_gt.csv",
                                                   "./datasets/mediaeval2017_testset_metadata.json")
    verify_pixels(mediaeval_test_df, "./results/result_mediaeval_2017_test.csv")

    mediaeval_train_df = get_flooded_mediaeval_info("./datasets/mediaeval2017_devset_gt.csv",
                                                    "./datasets/mediaeval2017_devset_metadata.json")
    verify_pixels(mediaeval_train_df, "./results/result_mediaeval_2017_train.csv")

    european_df = get_flooded_europeanfloods_info()
    verify_pixels(european_df, "./results/result_european_floods_2013.csv")


if __name__ == '__main__':
    gdal.UseExceptions()
    main()
