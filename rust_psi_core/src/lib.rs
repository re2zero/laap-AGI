/// LAAP PSI Core - Rust performance layer for Clifford algebra, multivectors, and rotors
/// Based on Geometric Algebra (Clifford Algebra) and Quantum Cognitive Models

use serde::{Deserialize, Serialize};

/// Multivector in Clifford Algebra Cl(n)
/// Contains scalar (grade 0), vector (grade 1), bivector (grade 2), trivector (grade 3) components
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
            bivector: vec![0.0; dim],
            trivector: vec![0.0; dim],
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

    /// Geometric product: ab = a·b + a∧b
    /// Inner product (semantic similarity) -> scalar
    /// Outer product (semantic relation) -> bivector
    pub fn geometric_product(&self, other: &Self) -> Self {
        let mut result = Self::new(self.vector.len());

        // Inner product: semantic similarity -> scalar
        let inner = self.vector.iter().zip(other.vector.iter()).map(|(a, b)| a * b).sum::<f64>();
        result.scalar = self.scalar * other.scalar + inner;

        // Outer product: semantic relation -> bivector
        // Approximated using Hadamard product
        result.bivector = self
            .vector
            .iter()
            .zip(other.vector.iter())
            .map(|(a, b)| a * b)
            .collect();

        // Normalize bivector
        let biv_norm = result.bivector.iter().map(|x| x * x).sum::<f64>().sqrt();
        if biv_norm > 1e-10 {
            result.bivector = result.bivector.into_iter().map(|x| x / biv_norm).collect();
        }

        // Vector component: weighted average
        if (self.scalar.abs() > 1e-10) && (other.scalar.abs() > 1e-10) {
            let sa = self.scalar.abs();
            let sb = other.scalar.abs();
            result.vector = self
                .vector
                .iter()
                .zip(other.vector.iter())
                .map(|(a, b)| *a * sb + *b * sa)
                .collect();
        } else if self.scalar.abs() > 1e-10 {
            result.vector = other.vector.clone();
        } else {
            result.vector = self
                .vector
                .iter()
                .zip(other.vector.iter())
                .map(|(a, b)| a + b)
                .collect();
        }

        // Normalize vector
        let vec_norm = result.vector.iter().map(|x| x * x).sum::<f64>().sqrt();
        if vec_norm > 1e-10 {
            result.vector = result.vector.into_iter().map(|x| x / vec_norm).collect();
        }

        result
    }

    /// Inner product — semantic similarity (a·b)
    pub fn inner_product(&self, other: &Self) -> f64 {
        self.vector.iter().zip(other.vector.iter()).map(|(a, b)| a * b).sum()
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

/// Rotor — rotation operator in semantic space
/// Rotor R = exp(-B/2) where B is a bivector.
/// R acts on vector v: v' = R · v · R†
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rotor {
    pub dim: usize,
    pub matrix: Vec<Vec<f64>>, // Orthogonal matrix representing the rotation
}

impl Rotor {
    /// Create a new rotor with the given dimension
    pub fn new(dim: usize) -> Self {
        Self {
            dim,
            matrix: vec![vec![0.0; dim]; dim],
        }
    }

    /// Learn rotation from source -> target using Kabsch-like optimal rotation
    pub fn learn(source: &Vec<f64>, target: &Vec<f64>) -> Self {
        let dim = source.len();
        let mut rot = Self::new(dim);

        // Normalize source and target
        let s_norm = source.iter().map(|x| x * x).sum::<f64>().sqrt();
        let t_norm = target.iter().map(|x| x * x).sum::<f64>().sqrt();

        let s: Vec<f64> = if s_norm > 1e-10 {
            source.iter().map(|x| x / s_norm).collect()
        } else {
            source.clone()
        };

        let t: Vec<f64> = if t_norm > 1e-10 {
            target.iter().map(|x| x / t_norm).collect()
        } else {
            target.clone()
        };

        // Cosine similarity
        let cos_theta = s.iter().zip(t.iter()).map(|(a, b)| a * b).sum::<f64>();
        let cos_theta = cos_theta.clamp(-1.0, 1.0);

        if (cos_theta - 1.0).abs() < 1e-4 {
            // Nearly same direction — identity matrix
            rot.matrix = (0..dim).map(|i| {
                let mut row = vec![0.0; dim];
                row[i] = 1.0;
                row
            }).collect();
            return rot;
        }

        if (cos_theta + 1.0).abs() < 1e-4 {
            // Opposite direction — negative identity (180 degree rotation)
            rot.matrix = (0..dim).map(|i| {
                let mut row = vec![0.0; dim];
                row[i] = -1.0;
                row
            }).collect();
            return rot;
        }

        // For two vectors, the optimal rotation is in the plane spanned by s and t
        // We construct a rotation matrix using the Householder-like reflection approach
        // or simple Givens rotation in the 2D plane

        // Calculate the rotation axis (perpendicular to both s and t in the plane)
        // In 3D or higher, we rotate in the s-t plane
        let mut rot_matrix = vec![vec![0.0; dim]; dim];

        // Initialize as identity
        for i in 0..dim {
            rot_matrix[i][i] = 1.0;
        }

        // Find the plane of rotation: s and t
        // We need to find two orthogonal vectors in the s-t plane
        let u = s.clone();

        // v = t - (t·u)u, then normalize
        let tu = t.iter().zip(u.iter()).map(|(a, b)| a * b).sum::<f64>();
        let mut v: Vec<f64> = t.iter().zip(u.iter()).map(|(ti, ui)| ti - tu * ui).collect();

        let v_norm = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if v_norm > 1e-10 {
            v = v.into_iter().map(|x| x / v_norm).collect();
        } else {
            // s and t are collinear (should have been caught by cos_theta check)
            for i in 0..dim {
                rot_matrix[i][i] = 1.0;
            }
            return rot;
        }

        // Now we have orthonormal basis: u (aligned with s) and v (perpendicular in plane)
        // We want to rotate u to align with t
        // t = cos_theta * u + sin_theta * v
        let sin_theta = (1.0 - cos_theta.powi(2)).sqrt();

        // Construct rotation matrix in the u-v plane
        for i in 0..dim {
            for j in 0..dim {
                // Start with identity
                let mut val = if i == j { 1.0 } else { 0.0 };

                // Subtract projections onto u and v planes
                val -= u[i] * u[j] + v[i] * v[j];

                // Add rotated components
                val += cos_theta * (u[i] * u[j] + v[i] * v[j]); // scaled by cos

                // Add cross terms for rotation
                val += sin_theta * (v[i] * u[j] - u[i] * v[j]);

                rot_matrix[i][j] = val;
            }
        }

        rot.matrix = rot_matrix;
        rot
    }

    /// Apply rotor to a vector
    pub fn apply(&self, v: &Vec<f64>) -> Vec<f64> {
        if self.matrix.is_empty() || self.matrix.len() != self.dim || self.matrix[0].len() != self.dim {
            return v.clone();
        }

        let mut result = vec![0.0; self.dim];
        for i in 0..self.dim {
            for j in 0..self.dim {
                result[i] += self.matrix[i][j] * v[j];
            }
        }

        // Normalize result
        let norm = result.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm > 1e-10 {
            result.into_iter().map(|x| x / norm).collect()
        } else {
            result
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_multivector_inner_product() {
        let mv1 = Multivector::from_vector(vec![1.0, 0.0, 0.0]);
        let mv2 = Multivector::from_vector(vec![0.0, 1.0, 0.0]);
        assert!( (mv1.inner_product(&mv2) - 0.0).abs() < 1e-10 );
    }

    #[test]
    fn test_rotor_learn() {
        let source = vec![1.0, 0.0, 0.0];
        let target = vec![0.0, 1.0, 0.0];
        let rotor = Rotor::learn(&source, &target);
        let applied = rotor.apply(&source);
        // Should be close to target
        assert!( (applied[0]).abs() < 1e-2 );
        assert!( (applied[1] - 1.0).abs() < 1e-2 );
    }
}