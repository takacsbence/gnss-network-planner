import math

from gnss_network_planner.utils.constants import *

# Glonass RK4 functions
def derivatives(state, eph):
    x, y, z, vx, vy, vz = state

    r2 = x * x + y * y + z * z
    r = math.sqrt(r2)
    z2 = z * z
    r5 = r2 * r2 * r

    k = 1.5 * J2 * MU_GLO * AE * AE / r5

    ax = (
        -MU_GLO * x / r**3
        - k * x * (1.0 - 5.0 * z2 / r2)
        + OMEGA_E_GLO**2 * x
        + 2.0 * OMEGA_E_GLO * vy
        + eph.ax*1000
    )

    ay = (
        -MU_GLO * y / r**3
        - k * y * (1.0 - 5.0 * z2 / r2)
        + OMEGA_E_GLO**2 * y
        - 2.0 * OMEGA_E_GLO * vx
        + eph.ay*1000
    )

    az = (
        -MU_GLO * z / r**3
        - k * z * (3.0 - 5.0 * z2 / r2)
        + eph.az*1000
    )

    return (vx, vy, vz, ax, ay, az)


def rk4_step(x, y, z, vx, vy, vz, eph, h):
    s = (x, y, z, vx, vy, vz)

    k1 = derivatives(s, eph)

    s2 = tuple(si + 0.5 * h * ki for si, ki in zip(s, k1))
    k2 = derivatives(s2, eph)

    s3 = tuple(si + 0.5 * h * ki for si, ki in zip(s, k2))
    k3 = derivatives(s3, eph)

    s4 = tuple(si + h * ki for si, ki in zip(s, k3))
    k4 = derivatives(s4, eph)

    return tuple(
        si + h / 6.0 * (k1i + 2.0 * k2i + 2.0 * k3i + k4i)
        for si, k1i, k2i, k3i, k4i in zip(s, k1, k2, k3, k4)
    )
