#!/bin/python

from cgi import print_form
import os
import struct
from time import sleep

FS_PATH = "/sys/kernel/ryzen_smu_drv/"

VER_PATH = FS_PATH + "version"
SMN_PATH = FS_PATH + "smn"
SMU_ARGS = FS_PATH + "smu_args"
RSMU_CMD = FS_PATH + "rsmu_cmd"
CN_PATH = FS_PATH + "codename"
PM_PATH = FS_PATH + "pm_table"


def is_root():
    return os.getenv("SUDO_USER") is not None or os.geteuid() == 0


def driver_loaded():
    return os.path.isfile(VER_PATH)


def pm_table_supported():
    return os.path.isfile(PM_PATH)


def read_file32(file):
    with open(file, "rb") as fp:
        result = fp.read(4)
        result = struct.unpack("<I", result)[0]
        fp.close()

    return result


def write_file32(file, value):
    with open(file, "wb") as fp:
        result = fp.write(struct.pack("<I", value))
        fp.close()

    return result == 4


def write_file64(file, value1, value2):
    with open(file, "wb") as fp:
        result = fp.write(struct.pack("<II", value1, value2))
        fp.close()

    return result == 8


def read_file192(file):
    with open(file, "rb") as fp:
        result = fp.read(24)
        result = struct.unpack("<IIIIII", result)
        fp.close()

    return result


def write_file192(file, v1, v2, v3, v4, v5, v6):
    with open(file, "wb") as fp:
        result = fp.write(struct.pack("<IIIIII", v1, v2, v3, v4, v5, v6))
        fp.close()

    return result == 24


def write_file192(file, v1, v2, v3, v4, v5, v6):
    with open(file, "wb") as fp:
        result = fp.write(struct.pack("<IIIIII", v1, v2, v3, v4, v5, v6))
        fp.close()

    return result == 24


def read_file_str(file, expectedLen=9):
    with open(file, "r") as fp:
        result = fp.read(expectedLen)
        fp.close()

    if expectedLen is not None and len(result) != expectedLen:
        print("Read file ({0}) failed with {1}".format(file, len(result)))
        return False

    return result


def read_smn_addr(addr):
    if write_file32(SMN_PATH, addr) == False:
        print("Failed to read SMN address: {:08X}".format(addr))
        return 0

    value = read_file32(SMN_PATH)

    if value == False:
        return 0

    return value


def write_smn_addr(addr, value):
    if write_file64(SMN_PATH, addr, value) == False:
        print(
            "Failed to write SMN address {:08X} with value: {:08X}".format(addr, value)
        )
        return False

    return True


def smu_command(op, arg1, arg2=0, arg3=0, arg4=0, arg5=0, arg6=0):
    check = True

    # Check if SMU is currently executing a command
    value = read_file32(RSMU_CMD)
    if value != False:
        while int(value) == 0:
            print("Wating for existing SMU command to complete ...")
            sleep(1)
            value = read_file32(RSMU_CMD)
    else:
        print("Failed to get SMU status response")
        return False

    # Write all arguments to the appropriate files
    if write_file192(SMU_ARGS, arg1, arg2, arg3, arg4, arg5, arg6) == False:
        print("Failed to write SMU arguments")
        return False

    # Write the command
    if write_file32(RSMU_CMD, op) == False:
        print("Failed to execute the SMU command: {:08X}".format(op))

    # Check for the result:
    value = read_file32(RSMU_CMD)
    if value != False:
        while value == 0:
            print("Wating for existing SMU command to complete ...")
            sleep(1)
            value = read_file32(RSMU_CMD)
    else:
        print("SMU OP readback returned false")
        return False

    if value != 1:
        print("SMU Command Result Failed: " + value)
        return False

    args = read_file192(SMU_ARGS)

    if args == False:
        print("Failed to read SMU response arguments")
        return False

    return args


def test_get_version():
    args = smu_command(0x02, 1)

    if args == False:
        return False

    v_test = "{:d}.{:d}.{:d}\n".format(
        args[0] >> 16 & 0xFF, args[0] >> 8 & 0xFF, args[0] & 0xFF
    )

    expected_version = read_file_str(VER_PATH, expectedLen=None)
    if v_test == expected_version:
        print("Retrieved SMU Version: v{0}".format(v_test.split("\n")[0]))
        return True

    print(f"SMU Test: Failed! Expected: {expected_version} Real: {v_test}")
    return False


def test_get_codename():
    codenames = [
        "Unspecified",
        "Colfax",
        "Renoir",
        "Picasso",
        "Matisse",
        "Threadripper",
        "Castle Peak",
        "Raven Ridge",
        "Raven Ridge 2",
        "Summit Ridge",
        "Pinnacle Ridge",
        "Rembrandt",
        "Vermeer",
        "Vangogh",
        "Cezanne",
        "Milan",
        "Dali",
        "Lucienne",
        "Naples",
        "Chagall",
        "Raphael",
        "Phoenix",
    ]
    args = read_file_str(CN_PATH, 3)

    if args != False and int(args) != 0 and int(args) < len(codenames):
        print("Processor Code Name: " + codenames[int(args)])
        return True

    print("Failed to detect processor code name!")
    return False


# [31-28] ccd index
# [27-24] ccx index (always 0 for Zen3 where each ccd has just one ccx)
# [23-20] core index
def make_core_mask(core=0, ccx=0, ccd=0):
    ccx_in_ccd = 1  # Assuming info_family == FAMILY_19H
    cores_in_ccx = 8 // ccx_in_ccd

    return (
        ((((ccd << 4) | (ccx % ccx_in_ccd) & 0xF)) << 4) | ((core % cores_in_ccx) & 0xF)
    ) << 20


def get_pbo_scalar() -> float:
    result = smu_command(0x6D, 0)
    if result == False:
        raise RuntimeError("get_pbo_scaler")
    return struct.unpack("<f", struct.pack("<I", result[0]))[0]


def set_pbo_scaler(scaler: float):
    arg1 = int(scaler * 100)
    result = smu_command(0x5B, arg1)
    if result == False:
        raise RuntimeError("set_pbo_scaler")


def get_psm_margin_core(core: int, ccx: int, ccd: int):
    coremask = make_core_mask(core, ccx, ccd)
    arg1 = coremask & 0xFFF00000
    result = smu_command(0xD5, arg1)
    if result == False:
        raise RuntimeError("get_psm_margin_core")
    return struct.unpack("<i", struct.pack("<I", result[0]))[0]


def make_psm_margin_arg(margin: int) -> int:
    # CO margin range seems to be from -30 to 30
    # Margin arg seems to be 16 bits (lowest 16 bits of the command arg)
    # Update 01 Nov 2022 - the range is different on Raphael, -40 is successfully set

    # if margin > 30:
    #     margin = 30
    # elif margin < -30:
    #     margin = -30

    offset = 0x100000 if margin < 0 else 0
    return (offset + margin) & 0xFFFF


def set_psm_margin_core(margin: int, core: int, ccx: int, ccd: int):
    m = make_psm_margin_arg(margin)
    coremask = make_core_mask(core, ccx, ccd)
    arg1 = (coremask & 0xFFF00000) | m
    result = smu_command(0x6, arg1)
    if result == False:
        raise RuntimeError("set_psm_margin_core")


def set_psm_margin_all(margin: int):
    arg1 = make_psm_margin_arg(margin)
    result = smu_command(0x7, arg1)
    if result == False:
        raise RuntimeError("set_psm_margin_all")


def main():
    if is_root() == False:
        print("Script must be run with root privileges.")
        return

    if driver_loaded() == False:
        print("The driver doesn't seem to be loaded.")
        return

    if test_get_version() == False:
        return

    if test_get_codename() == False:
        return

    if pm_table_supported():
        print("PM Table: Supported")
    else:
        print("PM Table: Unsupported")

    # 7950X: 2 ccx, 8 cores in each ccx
    cores_per_ccx = 8
    ccx_per_ccd = 1
    ccd_count = 2

    for ccd in range(ccd_count):
        for ccx in range(ccx_per_ccd):
            for core in range(cores_per_ccx):
                old_co = get_psm_margin_core(core, ccx, ccd)
                to_set = (
                    core + ccx * cores_per_ccx + ccd * cores_per_ccx * ccx_per_ccd - 15
                )
                set_psm_margin_core(to_set, core, ccx, ccd)
                co = get_psm_margin_core(core, ccx, ccd)
                mask = make_core_mask(core, ccx, ccd)
                print(
                    f"({ccd}, {ccx}, {core})[{mask:08x}]: {old_co} -> {to_set} -> {co}"
                )


main()
