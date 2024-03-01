import numpy as np
from typing import Any, BinaryIO
from struct import calcsize, pack, unpack


def _read_bytes_until(stream: BinaryIO, delimiter: bytes) -> bytes:
    """Read bytes from {stream} until the first encounter of {delimiter}.

    :arg stream: Stream object.
    :arg delimiter: Delimiter.

    :returns: Byte string.
    """
    return b''.join(until(lambda x: x == delimiter, stream.read, 1))


def _read_basic(stream: BinaryIO, endianness: str, basic_type: str) -> Any:
    """Read a value of basic type from a stream.

    :arg stream: Stream object.
    :arg endianness: Endianness.
    :arg basic_type: Type of {value}.

    :returns: Value of type {basic_type}.
    """
    if basic_type == 's':
        return _read_bytes_until(stream, b'\0')

    full_type = (endianness + basic_type).encode('utf-8')

    return unpack(full_type, stream.read(calcsize(full_type)))[0]


def _write_basic(
        stream: BinaryIO, endianness: str, basic_type: str, value: Any
        ) -> None:
    """Write a value of basic type to a stream.

    :arg stream: Stream object.
    :arg endianness: Endianness.
    :arg basic_type: Type of {value}.
    :arg value: Value to write.
    """
    if basic_type == 's':
        stream.write(value + b'\0')
        return
    elif isinstance(basic_type, np.ndarray):
        if basic_type.size != 0:
            assert basic_type[0] == value.size, f"Array size mismatch. Expected: {basic_type.basic_type[0]}, got: {value.size}"
        
        stream.write(value.tobytes())
        return

    full_type = (endianness + basic_type).encode('utf-8')
    stream.write(pack(full_type, cast(basic_type)(value)))


def cast(c_type: str) -> object:
    """Select the appropriate casting function given a C type.

    :arg c_type: C type.

    :returns: Casting function.
    """
    if c_type == '?':
        return bool
    if c_type in ['c', 's']:
        return bytes
    if c_type in ['f', 'd']:
        return float
    return int


def read(
        stream: BinaryIO, endianness: str, size_t: str, obj_type: Any
        ) -> Any:
    """Read an object from a stream.

    :arg stream: Stream object.
    :arg endianness: Endianness.
    :arg size_t: Type of size_t.
    :arg obj_type: Type object.

    :returns: Object of type {obj_type}.
    """
    if isinstance(obj_type, np.ndarray):
        length = _read_basic(stream, endianness, size_t)
        return np.frombuffer(
            stream.read(length * obj_type.itemsize), obj_type.dtype)
    
    if isinstance(obj_type, list):
        length = _read_basic(stream, endianness, size_t)
        
        return [
            read(stream, endianness, size_t, item) for _ in range(length)
            for item in obj_type]
    
    if isinstance(obj_type, tuple):
        return tuple(
            read(stream, endianness, size_t, item) for item in obj_type)
    
    return _read_basic(stream, endianness, obj_type)


def read_byte_string(stream: BinaryIO, endianness: str = None, size_bytes: int = None) -> bytes:
    if size_bytes is None:
        return _read_bytes_until(stream, b'\0')
    
    assert endianness is not None, "Endianness must be specified when size_bytes is specified"
    result = bytearray()
    while True:
        char = stream.read(1)
        if char == b'\0':
            break

        if char == b'#':
            size = str(int.from_bytes(stream.read(size_bytes), endianness))
            result.extend(size.encode('utf-8'))
            result.extend(read_byte_string(stream, endianness, size_bytes))
            break
        result.extend(char)

    return result
    

def write(
        stream: BinaryIO, endianness: str, size_t: str, obj_type: Any,
        obj: Any) -> None:
    """Write an object to a stream.

    :arg stream: Stream object.
    :arg endianness: Endianness.
    :arg size_t: Type of size_t.
    :arg obj_type: Type object.
    :arg obj: Object of type {obj_type}.
    """

    if isinstance(obj_type, list):
        _write_basic(stream, endianness, size_t, len(obj) // len(obj_type))
    if isinstance(obj_type, np.ndarray):
        _write_basic(stream, endianness, size_t, obj.size)
        _write_basic(stream, endianness, obj_type, obj)
    elif isinstance(obj_type, list) or isinstance(obj_type, tuple):
        for item_type, item in zip(obj_type * len(obj), obj):
            write(stream, endianness, size_t, item_type, item)
    else:
        _write_basic(stream, endianness, obj_type, obj)


def until(
        condition: callable, f: callable, *args: Any, **kwargs: Any) -> None:
    """Call {f(*args, **kwargs)} until {condition} is true.

    :arg condition: Function that inspects the result of {f}.
    :arg f: Any function.
    :arg *args: Porisional arguments of {f}.
    :arg **kwargs: Keyword arguments of {f}.
    """
    while True:
        result = f(*args, **kwargs)
        if condition(result):
            break
        yield result
