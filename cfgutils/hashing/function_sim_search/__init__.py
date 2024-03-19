mask64bit = 0xffffffffffffffff
mask32bit = 0xffffffff

def rotl64(data, n):
    _data = data & mask64bit
    return ((_data & mask64bit) << n) & mask64bit

# Some primes between 2^63 and 2^64 from CityHash.
seed0_ = 0xc3a5c85c97cb3127
seed1_ = 0xb492b66fbe98f273
seed2_ = 0x9ae16a3b2f90404f
k0 = seed0_
k1 = seed1_
k2 = seed2_

from .sim_hasher import FunctionSimHasher
