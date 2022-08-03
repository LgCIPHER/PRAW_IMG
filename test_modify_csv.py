import os.path

# File directory
dir_path = os.path.dirname(os.path.realpath(__file__))

csv_source_name = "Genshin_Wallpaper_img_list"
csv_source_path = os.path.join(
    dir_path, f"{csv_source_name}.csv")

csv_result_name = csv_source_name + "-v2"
csv_result_path = os.path.join(
    dir_path, f"{csv_result_name}.csv")

file_source = open(csv_source_path, mode="r", encoding="utf-8-sig")
file_result = open(csv_result_path, mode="w", encoding="utf-8-sig")

print("Hello!")
print("File location: " + str(csv_source_path))

header = "ID,URL\n"
file_result.write(header)

id = 1

row = file_source.readline().strip()

while row != "":
    row_new = str(id) + "," + row + "\n"

    file_result.write(row_new)

    id += 1

    row = file_source.readline().strip()

print("Done!")
