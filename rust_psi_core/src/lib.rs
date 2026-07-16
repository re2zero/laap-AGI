/// LAAP PSI Core - Rust performance layer for Clifford algebra, multivectors, and rotors
/// Based on Geometric Algebra (Clifford Algebra) and Quantum Cognitive Models
///
/// Reference:
/// - "Geometric Algebra for Computer Science" - Doran & Lasenby
/// - "Clifford Algebra to Geometric Algebra" - David Hestenes
/// - "Toward a Functional Geometric Algebra for Natural Language Semantics" - James Pustejovsky

pub mod multivector;
pub mod rotor;
pub mod pybridge;

pub use multivector::Multivector;
pub use rotor::Rotor;

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
    fn test_multivector_outer_product() {
        let mv1 = Multivector::from_vector(vec![1.0, 0.0, 0.0]); // e1
        let mv2 = Multivector::from_vector(vec![0.0, 1.0, 0.0]); // e2
        let outer = mv1.outer_product(&mv2);
        // e1 ∧ e2 should have bivector component at index 0 (for dim=3, bivector indices are (0,1), (0,2), (1,2))
        assert!( (outer.bivector[0] - 1.0).abs() < 1e-10 );
    }

    #[test]
    fn test_multivector_geometric_product() {
        let mv1 = Multivector::from_vector(vec![1.0, 0.0, 0.0]);
        let mv2 = Multivector::from_vector(vec![0.0, 1.0, 0.0]);
        let gp = mv1.geometric_product(&mv2);
        // Geometric product e1*e2 = e1∧e2 (bivector) + e1·e2 (scalar=0)
        assert!( (gp.scalar - 0.0).abs() < 1e-10 );
        assert!( (gp.bivector[0] - 1.0).abs() < 1e-10 );
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

    #[test]
    fn test_rotor_from_bivector() {
        // Create a bivector for rotation in the e1-e2 plane
        // B = (pi/2) * (e1 ∧ e2), so bivector component at index 0 is pi/2
        // This should rotate e1 towards e2 by 90 degrees (pi/2 radians)
        let dim = 3;
        let mut bivector = vec![0.0; dim * (dim - 1) / 2];
        let angle = std::f64::consts::PI / 2.0; // 90 degrees
        bivector[0] = angle; // e1 ∧ e2 with angle pi/2

        let rotor = Rotor::from_bivector(&bivector, dim);
        
        // Apply rotor to e1 = [1.0, 0.0, 0.0]
        let source = vec![1.0, 0.0, 0.0];
        let applied = rotor.apply(&source);
        
        // R = exp(-(pi/2)*(e1∧e2)/2) should rotate e1 towards e2 by 90 degrees
        // e1 -> e2 after 90 degree rotation
        assert!( (applied[0]).abs() < 1e-2, "applied[0] = {}", applied[0]);
        assert!( (applied[1] - 1.0).abs() < 1e-2, "applied[1] = {}", applied[1]);
    }
}