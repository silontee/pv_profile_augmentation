import utils.utils as utils
import os

utils.cp949_to_utf_8(
    os.path.join(utils.source_directory, "RPS 설비현황_24년 6월말 기준.csv")
)
