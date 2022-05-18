import dataclasses
from typing import Literal, Optional, Protocol, Tuple, runtime_checkable

import numpy as np
from isce3.io.gdal import Raster
from isce3.unwrap import snaphu
from numpy.typing import NDArray

__all__ = [
    "SnaphuUnwrap",
    "UnwrapCallback",
]


@runtime_checkable
class UnwrapCallback(Protocol):
    """Callback protocol for two-dimensional phase unwrapping algorithms.

    `UnwrapCallback` defines the abstract interface that unwrapping implementations are
    expected to conform to in order to "plug in" to the multi-scale unwrapping
    framework.
    """

    def __call__(
        self,
        igram: NDArray[np.complexfloating],
        corrcoef: NDArray[np.floating],
        nlooks: float,
        pwr: Optional[NDArray[np.floating]],
        mask: Optional[NDArray[np.bool_]],
        unwest: Optional[NDArray[np.floating]],
    ) -> Tuple[NDArray[np.floating], NDArray[np.unsignedinteger]]:
        """Perform two-dimensional phase unwrapping.

        Parameters
        ----------
        igram : numpy.ndarray
            Input interferogram.
        corrcoef : numpy.ndarray
            Sample correlation coefficient, normalized to the interval [0, 1], with the
            same shape as the input interferogram.
        nlooks : float
            Effective number of spatial looks used to form the input correlation data.
        pwr : numpy.ndarray or None, optional
            Optional average intensity of the two Single-Look Complex (SLC) images, in
            linear units, with the same shape as the input interferogram.
        mask : numpy.ndarray or None, optional
            Optional boolean mask of valid pixels, with the same shape as the input
            interferogram. A `True` value indicates that the corresponding pixel was
            valid. (default: None)
        unwest : numpy.ndarray or None, optional
            Optional initial estimate of the unwrapped phase, in radians, with the same
            shape as the input interferogram. (default: None)

        Returns
        -------
        unwphase : numpy.ndarray
            Unwrapped phase, in radians.
        conncomp : numpy.ndarray
            Connected component labels, with the same shape as the unwrapped phase.
        """
        ...


@dataclasses.dataclass
class SnaphuUnwrap(UnwrapCallback):
    """Callback functor for unwrapping using SNAPHU [1]_.

    Attributes
    ----------
    cost : {'topo', 'defo', 'smooth', 'p-norm'}
        Statistical cost mode.
    cost_params : isce3.unwrap.snaphu.CostParams or None
        Configuration parameters for the specified cost mode.
    init_method : {'mst', 'mcf'}
        Initialization method.

    References
    ----------
    .. [1] C. W. Chen and H. A. Zebker, "Two-dimensional phase unwrapping with use of
        statistical models for cost functions in nonlinear optimization," Journal of the
        Optical Society of America A, vol. 18, pp. 338-351 (2001).
    """

    cost: Literal["topo", "defo", "smooth", "p-norm"] = "smooth"
    cost_params: Optional[snaphu.CostParams] = None
    init_method: Literal["mst", "mcf"] = "mcf"

    def __post_init__(self):
        if self.cost not in {"topo", "defo", "smooth", "p-norm"}:
            raise ValueError(f"unexpected cost mode '{self.cost}'")
        if self.init_method not in {"mst", "mcf"}:
            raise ValueError(f"unexpected initialization method '{self.init_method}'")

    def __call__(
        self,
        igram: NDArray[np.complexfloating],
        corrcoef: NDArray[np.floating],
        nlooks: float,
        pwr: Optional[NDArray[np.floating]] = None,
        mask: Optional[NDArray[np.bool_]] = None,
        unwest: Optional[NDArray[np.floating]] = None,
    ) -> Tuple[NDArray[np.floating], NDArray[np.unsignedinteger]]:
        """Perform two-dimensional phase unwrapping using SNAPHU.

        Parameters
        ----------
        igram : numpy.ndarray
            Input interferogram.
        corrcoef : numpy.ndarray
            Sample correlation coefficient, normalized to the interval [0, 1], with the
            same shape as the input interferogram.
        nlooks : float
            Effective number of spatial looks used to form the input correlation data.
        pwr : numpy.ndarray or None, optional
            Optional average intensity of the two Single-Look Complex (SLC) images, in
            linear units, with the same shape as the input interferogram.
        mask : numpy.ndarray or None, optional
            Boolean mask of valid pixels, with the same shape as the input
            interferogram. A `True` value indicates that the corresponding pixel was
            valid. (default: None)
        unwest : numpy.ndarray or None, optional
            Initial estimate of the unwrapped phase, in radians, with the same shape as
            the input interferogram. (default: None)

        Returns
        -------
        unwphase : numpy.ndarray
            Unwrapped phase, in radians.
        conncomp : numpy.ndarray
            Connected component labels, with the same shape as the unwrapped phase.
        """
        # Convert input arrays to GDAL rasters with the expected datatypes.
        igram_data = np.asanyarray(igram, dtype=np.complex64)
        igram = Raster(igram_data)

        corrcoef_data = np.asanyarray(corrcoef, dtype=np.float32)
        corrcoef = Raster(corrcoef_data)

        if pwr is not None:
            pwr_data = np.asanyarray(pwr, dtype=np.float32)
            pwr = Raster(pwr_data)

        if mask is not None:
            mask_data = np.asanyarray(pwr, dtype=np.uint8)
            mask = Raster(mask_data)

        if unwest is not None:
            unwest_data = np.asanyarray(unwest, dtype=np.float32)
            unwest = Raster(unwest_data)

        # Get interferogram shape.
        shape = (igram.length, igram.width)

        # Create output arrays for unwrapped phase & connected component labels.
        unwphase = np.zeros(shape, dtype=np.float32)
        conncomp = np.zeros(shape, dtype=np.uint32)

        # Run SNAPHU.
        snaphu.unwrap(
            unw=Raster(unwphase),
            conncomp=Raster(conncomp),
            igram=igram,
            corr=corrcoef,
            nlooks=nlooks,
            cost=self.cost,
            cost_params=self.cost_params,
            init_method=self.init_method,
            pwr=pwr,
            mask=mask,
            unwest=unwest,
        )

        return unwphase, conncomp
