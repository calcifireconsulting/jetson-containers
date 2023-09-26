#!/usr/bin/env python3
# exposes cudaKNN() and cudaL2Norm() functions from fiass_lite.cu to Python via ctypes
# see benchmark.py for example usage from Python
import os
import math
import ctypes as C
import numpy as np
    
from cuda import cuda, nvrtc

from cuda.cudart import (
    cudaMallocManaged, 
    cudaMemAttachGlobal, 
    cudaGetLastError,
    cudaGetErrorString,
    cudaError_t
)

_lib = C.CDLL('/opt/faiss_lite/build/libfaiss_lite.so')

# https://github.com/facebookresearch/faiss/blob/main/faiss/MetricType.h
DistanceMetrics = {
    'inner_product': 0,
    'l2': 1,
    'l1': 2,
    'Linf': 3,
    'canberra': 20,
    'braycurtis': 21,
    'jensenshannon': 22,
    'jaccard': 23,
}

def _cudaKNN(name='cudaKNN'):
    func = _lib[name]
    
    func.argtypes = [
        C.c_void_p, # vectors
        C.c_void_p, # queries
        C.c_int,    # dsize
        C.c_int,    # n
        C.c_int,    # m
        C.c_int,    # d
        C.c_int,    # k
        C.c_int,    # metric
        C.POINTER(C.c_float), # vector_norms
        C.POINTER(C.c_float), # out_distances
        C.POINTER(C.c_longlong), # out_indices
        C.c_void_p, # cudaStream_t
    ]
    
    func.restype = C.c_bool
    return func
 
def _cudaL2Norm(name='cudaL2Norm'):
    func = _lib[name]
    
    func.argtypes = [
        C.c_void_p, # vectors
        C.c_int,    # dsize
        C.c_int,    # n
        C.c_int,    # d
        C.POINTER(C.c_float), # output
        C.c_bool,   # squared
        C.c_void_p, # cudaStream_t
    ]
    
    func.restype = C.c_bool
    return func
    
cudaKNN = _cudaKNN()
cudaL2Norm = _cudaL2Norm()


def dtype_to_ctype(dtype):
    if dtype == np.float32:
        return C.c_float
    elif dtype == np.float16:
        return C.c_ushort
    elif dtype == np.int32:
        return C.c_int
    elif dtype == np.int64:
        return C.c_longlong
    else:
        raise RuntimeError(f"unsupported dtype:  {dtype}")
  
def cudaAllocMapped(shape, dtype):
    """
    Allocate cudaMallocManaged() memory and map it to a numpy array
    """
    dsize = np.dtype(dtype).itemsize

    if isinstance(shape, int):
        size = shape * dsize
        shape = [shape]
    else:
        size = math.prod(shape) * dsize
    
    print(f"-- allocating {size} bytes ({size/(1024*1024):.2f} MB) with cudaMallocManaged()")
    
    err, ptr = cudaMallocManaged(size, cudaMemAttachGlobal)
    assert_cuda(err)
    
    return cudaToNumpy(ptr, shape, dtype), ptr
        
def cudaToNumpy(ptr, shape, dtype):
    """
    Map a shared CUDA pointer into np.ndarray with the given shape and datatype.
    The pointer should have been allocated with cudaMallocManaged() or using cudaHostAllocMapped,
    and the user is responsible for any CPU/GPU synchronization (i.e. by using cudaStreams)
    """
    array = np.ctypeslib.as_array(C.cast(ptr, C.POINTER(dtype_to_ctype(dtype))), shape=shape)
    
    if dtype == np.float16:
        array.dtype = np.float16
       
    return array
 
def assert_cuda(err):
    """
    Throw a runtime exception if a CUDA error occurred
    """
    if isinstance(err, tuple) and len(err) == 1:
        err = err[0]
        
    if isinstance(err, cuda.CUresult):
        if err != cuda.CUresult.CUDA_SUCCESS:
            raise RuntimeError(f"CUDA Error {err} -- {cudaGetErrorString(err)[1]}")
    elif isinstance(err, cudaError_t):
        if err != cudaError_t.cudaSuccess:
            raise RuntimeError(f"CUDA Error {err} -- {cudaGetErrorString(err)[1]}")
    elif isinstance(err, nvrtc.nvrtcResult):
        if err != nvrtc.nvrtcResult.NVRTC_SUCCESS:
            raise RuntimeError(f"nvrtc Error {err}")
    else:
        raise RuntimeError(f"Unknown error type: {err}") 
 