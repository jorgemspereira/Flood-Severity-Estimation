from pathlib import Path

import gdal
import numpy as np
import pandas as pd
from gdal import gdalconst
from tqdm import tqdm

from utils.dataset_utils import get_flooded_mediaeval_info, get_flooded_europeanfloods_info, replace_class
from utils.dem_utils import read_request, make_request_dsm, merge_dsm, fill_no_data, get_geotiff_info, \
    get_position_in_raster
from utils.plot_utils import draw_plot


def get_8_neighbors_position(current_position):
    row, col = current_position[0], current_position[1]
    return [(row - x, col - y) for x in range(-1, 2) for y in range(-1, 2) if x != 0 or y != 0]


def get_24_neighbors_position(current_position):
    row, col = current_position[0], current_position[1]
    return [(row - x, col - y) for x in range(-2, 3) for y in range(-2, 3) if x != 0 or y != 0]


def get_48_neighbors_position(current_position):
    row, col = current_position[0], current_position[1]
    return [(row - x, col - y) for x in range(-3, 4) for y in range(-3, 4) if x != 0 or y != 0]


def get_80_neighbors_position(current_position):
    row, col = current_position[0], current_position[1]
    return [(row - x, col - y) for x in range(-4, 5) for y in range(-4, 5) if x != 0 or y != 0]


def get_120_neighbors_position(current_position):
    row, col = current_position[0], current_position[1]
    return [(row - x, col - y) for x in range(-5, 6) for y in range(-5, 6) if x != 0 or y != 0]


def get_168_neighbors_position(current_position):
    row, col = current_position[0], current_position[1]
    return [(row - x, col - y) for x in range(-6, 7) for y in range(-6, 7) if x != 0 or y != 0]


def get_differences(current_pos, positions, dsm_info):
    return [abs(dsm_info[-1][pos[0]][pos[1]] - dsm_info[-1][current_pos[0]][current_pos[1]]) for pos in positions]


def flood_severity_estimation(row):
    result = {}
    longitude, latitude = row['longitude'], row['latitude']
    longitude_converted, latitude_converted = row['longitude_converted'], row['latitude_converted']

    dsm_content = read_request(make_request_dsm(latitude_converted, longitude_converted), "/vsimem/dsm")
    dsm_content = merge_dsm(row, dsm_content, "/vsimem/dsm_merged")
    dsm_content = fill_no_data(dsm_content, "/vsimem/dsm_final")

    dsm_content = gdal.Translate("/vsimem/dsm_high_res", dsm_content, format="GTiff", widthPct=300,
                                 heightPct=300, resampleAlg=gdalconst.GRA_CubicSpline)

    dsm_info = get_geotiff_info(dsm_content)
    init_position = get_position_in_raster(longitude, latitude, dsm_info)

    eight_neighbors = get_8_neighbors_position(init_position)
    eight_neighbors_diffs = get_differences(init_position, eight_neighbors, dsm_info)
    result["eight_neighbors_avg"] = np.mean(eight_neighbors_diffs)
    result["eight_neighbors_min"] = min(eight_neighbors_diffs)
    result["eight_neighbors_max"] = max(eight_neighbors_diffs)

    twenty_four_neighbors = get_24_neighbors_position(init_position)
    twenty_four_neighbors_diffs = get_differences(init_position, twenty_four_neighbors, dsm_info)
    result["twenty_four_neighbors_avg"] = np.mean(twenty_four_neighbors_diffs)
    result["twenty_four_neighbors_min"] = min(twenty_four_neighbors_diffs)
    result["twenty_four_neighbors_max"] = max(twenty_four_neighbors_diffs)

    forty_eight_neighbors = get_48_neighbors_position(init_position)
    forty_eight_diffs = get_differences(init_position, forty_eight_neighbors, dsm_info)
    result["forty_eight_neighbors_avg"] = np.mean(forty_eight_diffs)
    result["forty_eight_neighbors_min"] = min(forty_eight_diffs)
    result["forty_eight_neighbors_max"] = max(forty_eight_diffs)

    eighty_neighbors = get_80_neighbors_position(init_position)
    eighty_neighbors_diffs = get_differences(init_position, eighty_neighbors, dsm_info)
    result["eighty_neighbors_avg"] = np.mean(eighty_neighbors_diffs)
    result["eighty_neighbors_min"] = min(eighty_neighbors_diffs)
    result["eighty_neighbors_max"] = max(eighty_neighbors_diffs)

    one_hundred_twenty_neighbors = get_120_neighbors_position(init_position)
    one_hundred_twenty_neighbors_diffs = get_differences(init_position, one_hundred_twenty_neighbors, dsm_info)
    result["one_hundred_twenty_neighbors_avg"] = np.mean(one_hundred_twenty_neighbors_diffs)
    result["one_hundred_twenty_neighbors_min"] = min(one_hundred_twenty_neighbors_diffs)
    result["one_hundred_twenty_neighbors_max"] = max(one_hundred_twenty_neighbors_diffs)

    one_hundred_sixty_eight_neighbors = get_168_neighbors_position(init_position)
    one_hundred_sixty_eight_neighbors_diffs = get_differences(init_position, one_hundred_sixty_eight_neighbors, dsm_info)
    result["one_hundred_sixty_eight_neighbors_avg"] = np.mean(one_hundred_sixty_eight_neighbors_diffs)
    result["one_hundred_sixty_eight_neighbors_min"] = min(one_hundred_sixty_eight_neighbors_diffs)
    result["one_hundred_sixty_eight_neighbors_max"] = max(one_hundred_sixty_eight_neighbors_diffs)

    gdal.Unlink("/vsimem/dsm_high_res")
    return result


def get_values(data_frame, font, output_name):
    columns_names = ['filename', 'class', 'font', 'eight_neighbors_avg', 'eight_neighbors_min', 'eight_neighbors_max',
                     'twenty_four_neighbors_avg', 'twenty_four_neighbors_min', 'twenty_four_neighbors_max',
                     'forty_eight_neighbors_avg', 'forty_eight_neighbors_min', 'forty_eight_neighbors_max',
                     'eighty_neighbors_avg', 'eighty_neighbors_min', 'eighty_neighbors_max',
                     'one_hundred_twenty_neighbors_avg', 'one_hundred_twenty_neighbors_min',
                     'one_hundred_twenty_neighbors_max', 'one_hundred_sixty_eight_neighbors_avg',
                     'one_hundred_sixty_eight_neighbors_min', 'one_hundred_sixty_eight_neighbors_max']

    if Path(output_name).is_file():
        result_df = pd.read_csv(output_name)
    else:
        result_df = pd.DataFrame(columns=columns_names)

    progress_bar = tqdm(total=data_frame.shape[0])
    for index, row in data_frame.iterrows():
        progress_bar.update(1)

        if str(row['filename']) not in result_df['filename'].values.astype(str):
            try:
                result = flood_severity_estimation(row)
            except (RuntimeError, TypeError):
                continue

            result['filename'] = str(row['filename'])
            result['class'] = int(row['class'])
            result['font'] = font

            result_df.loc[len(result_df)] = result
            result_df.to_csv(output_name, index=False)

    return result_df


def main():
    mediaeval_test_df = get_flooded_mediaeval_info("./datasets/mediaeval2017_testset_gt.csv",
                                                   "./datasets/mediaeval2017_testset_metadata.json")
    result_mediaeval_test = get_values(mediaeval_test_df,
                                       font="mediaeval_2017_test",
                                       output_name="./values_plots_dem/values_mediaeval_test.csv")

    mediaeval_train_df = get_flooded_mediaeval_info("./datasets/mediaeval2017_devset_gt.csv",
                                                    "./datasets/mediaeval2017_devset_metadata.json")
    result_mediaeval_train = get_values(mediaeval_train_df,
                                        font="mediaeval_2017_train",
                                        output_name="./values_plots_dem/values_mediaeval_train.csv")

    european_df = get_flooded_europeanfloods_info()
    result_european_floods = get_values(european_df,
                                        font="european_floods_2013",
                                        output_name="./values_plots_dem/values_european_floods.csv")

    result = result_mediaeval_test.append(result_mediaeval_train, ignore_index=True)
    result = result.append(result_european_floods, ignore_index=True)
    result = replace_class(result)
    draw_plot(result)


if __name__ == '__main__':
    gdal.UseExceptions()
    main()
