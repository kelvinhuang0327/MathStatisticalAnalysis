"""Roots of unity for the NumPy 1.26.2 real FFT used in the frozen donor.

The reduced-angle polynomials and evaluation order follow my_sincosm1pi and
calc_first_octant in numpy/fft/_pocketfft.c (NumPy v1.26.2, Martin Reinecke).
"""

# Copyright (C) 2004-2018 Max-Planck-Society. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * Neither the name of the copyright holder nor the names of its contributors
#   may be used to endorse or promote products derived from this software
#   without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import math

_COS_MINUS_ONE = (
    -1.0369917389758117e-4,
    1.9294935641298806e-3,
    -2.5806887942825395e-2,
    2.3533063028328211e-1,
    -1.3352627688538006,
    4.0587121264167623,
    -4.9348022005446790,
)
_SIN = (
    4.6151442520157035e-4,
    -7.3700183130883555e-3,
    8.2145868949323936e-2,
    -5.9926452893214921e-1,
    2.5501640398732688,
    -5.1677127800499516,
)


def _polynomial(x: float, coefficients: tuple[float, ...]) -> float:
    value = coefficients[0]
    for coefficient in coefficients[1:]:
        value = math.fma(value, x, coefficient)
    return value


def _reduced_angle(index: int, denominator: int) -> tuple[float, float]:
    angle = 2.0 * index / denominator
    square = angle * angle
    cosine_minus_one = square * _polynomial(square, _COS_MINUS_ONE)
    sine_remainder = (square * angle) * _polynomial(square, _SIN)
    return cosine_minus_one, math.fma(angle, math.pi, sine_remainder)


def numpy_126_twiddles(length: int) -> tuple[tuple[float, float], ...]:
    """Construct the first octant in blocks, then reflect it using integer indices."""
    denominator = math.lcm(length, 4)
    count = (denominator + 4) // 8
    block = math.isqrt(count)
    offsets = [_reduced_angle(j, denominator) for j in range(block)]
    octant = [(1.0 + dc, sn) for dc, sn in offsets]
    for start in range(block, count, block):
        dc, sn = _reduced_angle(start, denominator)
        octant.append((1.0 + dc, sn))
        for oc, os in offsets[1 : min(block, count - start)]:
            octant.append((((dc * oc - sn * os + dc) + oc) + 1.0, (dc * os + sn * oc) + sn + os))
    if denominator % 8 == 0:
        octant.append((math.sqrt(0.5), math.sqrt(0.5)))

    quarter = denominator // 4
    table = []
    for index in range(length):
        quadrant, offset = divmod(index * (denominator // length), quarter)
        if offset * 2 <= quarter:
            co, si = octant[offset]
        else:
            si, co = octant[quarter - offset]
        table.append(((co, si), (-si, co), (-co, -si), (si, -co))[quadrant])
    return tuple(table)
