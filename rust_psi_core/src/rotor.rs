/// Rotor — rotation operator in semantic space
/// Rotor R = exp(-B/2) where B is a bivector.
/// R acts on vector v: v' = R · v · R†
///
/// Reference:
/// - "Geometric Algebra for Computer Science" - Doran & Lasenby
/// - "Clifford Algebra to Geometric Algebra" - David Hestenes

use serde::{Deserialize, Serialize};

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

    /// Create a rotor from a bivector using the exponential map: R = exp(-B/2)
    /// For a bivector B = sum(b_{ij} * e_i∧e_j), the rotor is:
    /// R = product over i<j of: cos(b_{ij}/2) - (e_i∧e_j)*sin(b_{ij}/2)
    /// This generates rotations in each i-j plane with angle b_{ij}
    pub fn from_bivector(bivector: &Vec<f64>, dim: usize) -> Self {
        let mut rot = Self::new(dim);

        // Initialize as identity
        for i in 0..dim {
            rot.matrix[i][i] = 1.0;
        }

        // Construct rotation matrix from bivector
        // For each bivector component corresponding to e_i ∧ e_j, it generates rotation in the i-j plane
        // The rotation angle is b_{ij}
        let mut biv_idx = 0;
        for i in 0..dim {
            for j in (i + 1)..dim {
                if biv_idx < bivector.len() {
                    let b_component = bivector[biv_idx];
                    
                    // Rotation angle in the i-j plane is b_component
                    let angle = b_component;
                    let c = angle.cos();
                    let s = angle.sin();

                    // Rotation in the i-j plane:
                    // R_ii = c, R_jj = c
                    // R_ij = -s, R_ji = s
                    rot.matrix[i][i] *= c;
                    rot.matrix[j][j] *= c;
                    rot.matrix[i][j] -= s;
                    rot.matrix[j][i] += s;
                }
                biv_idx += 1;
            }
        }

        rot
    }

    /// Learn rotation from source -> target using optimal rotation in the s-t plane
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