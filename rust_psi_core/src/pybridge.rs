/// PyO3 bridge for LAAP PSI Core
/// Provides Python bindings for Multivector and Rotor

use pyo3::prelude::*;
use crate::multivector::Multivector;
use crate::rotor::Rotor;

#[pyclass]
#[derive(Clone, Debug)]
pub struct PyMultivector {
    #[pyo3(get, set)]
    pub scalar: f64,
    #[pyo3(get, set)]
    pub vector: Vec<f64>,
    #[pyo3(get, set)]
    pub bivector: Vec<f64>,
    #[pyo3(get, set)]
    pub trivector: Vec<f64>,
}

#[pymethods]
impl PyMultivector {
    #[new]
    fn new(dim: usize) -> Self {
        let mv = Multivector::new(dim);
        Self {
            scalar: mv.scalar,
            vector: mv.vector,
            bivector: mv.bivector,
            trivector: mv.trivector,
        }
    }

    #[staticmethod]
    fn from_vector(v: Vec<f64>) -> Self {
        let mv = Multivector::from_vector(v);
        Self {
            scalar: mv.scalar,
            vector: mv.vector,
            bivector: mv.bivector,
            trivector: mv.trivector,
        }
    }

    fn inner_product(&self, other: &PyMultivector) -> f64 {
        let mv1 = Multivector {
            scalar: self.scalar,
            vector: self.vector.clone(),
            bivector: self.bivector.clone(),
            trivector: self.trivector.clone(),
        };
        let mv2 = Multivector {
            scalar: other.scalar,
            vector: other.vector.clone(),
            bivector: other.bivector.clone(),
            trivector: other.trivector.clone(),
        };
        mv1.inner_product(&mv2)
    }

    fn outer_product(&self, other: &PyMultivector) -> PyMultivector {
        let mv1 = Multivector {
            scalar: self.scalar,
            vector: self.vector.clone(),
            bivector: self.bivector.clone(),
            trivector: self.trivector.clone(),
        };
        let mv2 = Multivector {
            scalar: other.scalar,
            vector: other.vector.clone(),
            bivector: other.bivector.clone(),
            trivector: other.trivector.clone(),
        };
        let result = mv1.outer_product(&mv2);
        PyMultivector {
            scalar: result.scalar,
            vector: result.vector,
            bivector: result.bivector,
            trivector: result.trivector,
        }
    }

    fn geometric_product(&self, other: &PyMultivector) -> PyMultivector {
        let mv1 = Multivector {
            scalar: self.scalar,
            vector: self.vector.clone(),
            bivector: self.bivector.clone(),
            trivector: self.trivector.clone(),
        };
        let mv2 = Multivector {
            scalar: other.scalar,
            vector: other.vector.clone(),
            bivector: other.bivector.clone(),
            trivector: other.trivector.clone(),
        };
        let result = mv1.geometric_product(&mv2);
        PyMultivector {
            scalar: result.scalar,
            vector: result.vector,
            bivector: result.bivector,
            trivector: result.trivector,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "PyMultivector(scalar={}, vector={:?}, bivector={:?}, trivector={:?})",
            self.scalar, self.vector, self.bivector, self.trivector
        )
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PyRotor {
    #[pyo3(get, set)]
    pub dim: usize,
    #[pyo3(get, set)]
    pub matrix: Vec<Vec<f64>>,
}

#[pymethods]
impl PyRotor {
    #[new]
    fn new(dim: usize) -> Self {
        let rotor = Rotor::new(dim);
        Self {
            dim: rotor.dim,
            matrix: rotor.matrix,
        }
    }

    #[staticmethod]
    fn from_bivector(bivector: Vec<f64>, dim: usize) -> Self {
        let rotor = Rotor::from_bivector(&bivector, dim);
        Self {
            dim: rotor.dim,
            matrix: rotor.matrix,
        }
    }

    #[staticmethod]
    fn learn(source: Vec<f64>, target: Vec<f64>) -> Self {
        let rotor = Rotor::learn(&source, &target);
        Self {
            dim: rotor.dim,
            matrix: rotor.matrix,
        }
    }

    fn apply(&self, v: Vec<f64>) -> Vec<f64> {
        let rotor = Rotor {
            dim: self.dim,
            matrix: self.matrix.clone(),
        };
        rotor.apply(&v)
    }

    fn __repr__(&self) -> String {
        format!("PyRotor(dim={}, matrix={:?})", self.dim, self.matrix)
    }
}

#[pymodule]
fn laap_psi_core(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyMultivector>()?;
    m.add_class::<PyRotor>()?;
    Ok(())
}