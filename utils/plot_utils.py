import matplotlib.pyplot as plt
import pandas as pd


def draw_plot(result):
    eight_neighbors_ones_avg = result[result['class'] == 1].eight_neighbors_avg.tolist()
    eight_neighbors_ones_min = result[result['class'] == 1].eight_neighbors_min.tolist()

    a_less_b = [eight_neighbors_ones_avg[index] - eight_neighbors_ones_min[index]
                for index in range(0, len(eight_neighbors_ones_avg))]

    heights_ones = [min(1.0, eight_neighbors_ones_avg[index] - eight_neighbors_ones_min[index])
                    for index in range(0, len(eight_neighbors_ones_avg))]

    print("Class LESS than 1 meter.")
    print("Number of zeros   : {:05.2f} %".format(100 * sum(x == 0 for x in heights_ones) / len(heights_ones)))
    print("Above 1 meter     : {:05.2f} %".format(100 * sum(x > 1.0 for x in a_less_b) / len(a_less_b)))

    twenty_four_neighbors_twos_avg = result[result['class'] == 2].twenty_four_neighbors_avg.tolist()
    twenty_four_neighbors_twos_max = result[result['class'] == 2].twenty_four_neighbors_max.tolist()

    forty_eight_neighbors_twos_avg = result[result['class'] == 2].forty_eight_neighbors_avg.tolist()
    forty_eight_neighbors_twos_max = result[result['class'] == 2].forty_eight_neighbors_max.tolist()

    heights_twos, a_less_b = [], []
    for index in range(0, len(twenty_four_neighbors_twos_avg)):
        height = twenty_four_neighbors_twos_max[index] - twenty_four_neighbors_twos_avg[index]
        if height < 1.0:
            height = forty_eight_neighbors_twos_max[index] - forty_eight_neighbors_twos_avg[index]

        a_less_b.append(height)
        heights_twos.append(max(1.0, height))

    print("Class MORE than 1 meter.")
    print("Above 3 meters    : {:05.2f} %".format(100 * sum(x > 3.0 for x in heights_twos) / len(heights_twos)))
    print("Above 5 meters    : {:05.2f} %".format(100 * sum(x > 5.0 for x in heights_twos) / len(heights_twos)))
    print("Less than 1 meter : {:05.2f} %".format(100 * sum(x < 1.0 and x != 0 for x in a_less_b) / len(a_less_b)))
    print("Number of zeros   : {:05.2f} %".format(100 * sum(x == 0 for x in a_less_b) / len(a_less_b)))

    fig, ax = plt.subplots()
    bp1 = ax.boxplot(heights_ones, positions=[1], patch_artist=True)
    bp2 = ax.boxplot(heights_twos, positions=[2], patch_artist=True)

    bp1['boxes'][0].set_facecolor("lightblue")
    bp2['boxes'][0].set_facecolor("lightgreen")

    ax.set_xlim(0, 3)
    ax.set_ylim(-0.1, 7.5)
    plt.xticks([1, 2], ["Less 1M\n", "More 1M\n"], rotation=45)
    plt.title('Heights')

    fig.tight_layout()
    plt.savefig('heights.png')

    final_result = []
    for index, row in result.iterrows():
        if row['class'] == 1:
            value = heights_ones.pop(0)
        if row['class'] == 2:
            value = heights_twos.pop(0)
        final_result.append((row['filename'], row['class'], value))

    df = pd.DataFrame(final_result, columns=['filename', 'class', 'height'])
    df.to_csv("result.csv", index=False)
