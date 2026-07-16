/// Multivector in Clifford Algebra Cl(n)
/// Contains scalar (grade 0), vector (grade 1), bivector (grade 2), trivector (grade 3) components
///
/// Reference:
/// - "Geometric Algebra for Computer Science" - Doran & Lasenby
/// - "Clifford Algebra to Geometric Algebra" - David Hestenes

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Multivector {
    pub scalar: f64,              // grade 0 — concept strength/weight
    pub vector: Vec<f64>,         // grade 1 — semantic direction
    pub bivector: Vec<f64>,       // grade 2 — relationships (compressed representation)
    pub trivector: Vec<f64>,      // grade 3 — meta-relationships
}

impl Multivector {
    /// Create a new multivector with the given dimension
    pub fn new(dim: usize) -> Self {
        Self {
            scalar: 0.0,
            vector: vec![0.0; dim],
            bivector: vec![0.0; dim * (dim - 1) / 2], // bivector components: C(n,2)
            trivector: vec![0.0; dim * (dim - 1) * (dim - 2) / 6], // trivector components: C(n,3)
        }
    }

    /// Create a multivector from a semantic vector
    pub fn from_vector(v: Vec<f64>) -> Self {
        let dim = v.len();
        let mut mv = Self::new(dim);
        // Normalize the vector
        let norm = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm > 1e-10 {
            mv.vector = v.into_iter().map(|x| x / norm).collect();
        } else {
            mv.vector = v;
        }
        mv
    }

    /// Outer product (wedge product): a ∧ b
    /// For two vectors, the outer product is a bivector: a ∧ b = (ab - ba)/2
    pub fn outer_product(&self, other: &Self) -> Self {
        let dim = self.vector.len();
        let mut result = Self::new(dim);

        // Compute bivector components from outer product of vectors
        // For basis vectors e_i ∧ e_j, the component is at index corresponding to (i,j) with i < j
        let mut biv_idx = 0;
        for i in 0..dim {
            for j in (i + 1)..dim {
                // (a ∧ b)_{ij} = a_i * b_j - a_j * b_i
                let component = self.vector[i] * other.vector[j] - self.vector[j] * other.vector[i];
                if biv_idx < result.bivector.len() {
                    result.bivector[biv_idx] = component;
                }
                biv_idx += 1;
            }
        }

        result
    }

    /// Inner product — semantic similarity (a·b)
    pub fn inner_product(&self, other: &Self) -> f64 {
        self.vector.iter().zip(other.vector.iter()).map(|(a, b)| a * b).sum()
    }

    /// Geometric product: ab = a·b + a∧b
    /// Inner product (semantic similarity) -> scalar
    /// Outer product (semantic relation) -> bivector
    pub fn geometric_product(&self, other: &Self) -> Self {
        let mut result = Self::new(self.vector.len());

        // Inner product: semantic similarity -> scalar
        let inner = self.inner_product(other);
        result.scalar = self.scalar * other.scalar + inner;

        // Outer product: semantic relation -> bivector
        let outer = self.outer_product(other);
        result.bivector = outer.bivector;

        // Vector component: for pure vectors, geometric product has no vector component
        // unless there are scalar or higher-grade components
        if self.scalar.abs() > 1e-10 && other.scalar.abs() > 1e-10 {
            // Weighted average for vector components if both have scalars
            let sa = self.scalar.abs();
            let sb = other.scalar.abs();
            result.vector = self
                .vector
                .iter()
                .zip(other.vector.iter())
                .map(|(a, b)| *a * sb + *b * sa)
                .collect();
            
            // Normalize vector
            let vec_norm = result.vector.iter().map(|x| x * x).sum::<f64>().sqrt();
            if vec_norm > 1e-10 {
                result.vector = result.vector.into_iter().map(|x| x / vec_norm).collect();
            }
        } else if self.scalar.abs() > 1e-10 {
            result.vector = other.vector.clone();
        } else if other.scalar.abs() > 1e-10 {
            result.vector = self.vector.clone();
        }

        result
    }

    /// Compute B^2 for a bivector B (result is a scalar)
    /// For a bivector B, B^2 is a scalar (typically negative)
    pub fn bivector_squared_scalar(biv: &Vec<f64>) -> f64 {
        // For bivector components in Cl(n), the square is sum of -biv[i]^2
        // because e_i ∧ e_j squared = -1 for orthonormal basis
        let mut sum = 0.0;
        for b in biv {
            sum -= b * b;
        }
        sum
    }

    /// Norm of the bivector part
    pub fn bivector_norm(&self) -> f64 {
        let b2 = Self::bivector_squared_scalar(&self.bivector);
        if b2 < 0.0 {
            (-b2).sqrt()
        } else if b2 > 0.0 {
            b2.sqrt()
        } else {
            0.0
        }
    }

    /// Norm of the multivector
    pub fn norm(&self) -> f64 {
        (self.scalar.powi(2)
            + self.vector.iter().map(|x| x * x).sum::<f64>()
            + self.bivector.iter().map(|x| x * x).sum::<f64>()
            + self.trivector.iter().map(|x| x * x).sum::<f64>())
        .sqrt()
    }
}