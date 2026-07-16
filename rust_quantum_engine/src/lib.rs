/// LAAP Quantum Engine - Rust performance layer for quantum cognition models
/// Based on Quantum Probability Models and Quantum Cognition Theory
///
/// Reference:
/// - "Quantum Models of Cognition and Decision" - Jerome R. Busemeyer, Peter D. Bruza
/// - "Quantum Cognition" - Various authors

use complex::c64;
use std::f64::consts::PI;

// Include PyO3 bridge module
mod pybridge;

/// Quantum State Vector for multi-qubit systems
#[derive(Debug, Clone)]
pub struct QuantumState {
    pub num_qubits: usize,
    pub amplitudes: Vec<c64>, // Complex amplitudes for 2^num_qubits states
}

impl QuantumState {
    /// Create a new quantum state with the given number of qubits
    pub fn new(num_qubits: usize) -> Self {
        let dim = 1usize << num_qubits; // 2^num_qubits
        Self {
            num_qubits,
            amplitudes: vec![c64(0.0, 0.0); dim],
        }
    }

    /// Create a quantum state from real values (initializes imaginary parts to 0)
    pub fn from_real(values: Vec<f64>) -> Self {
        let dim = values.len();
        let num_qubits = dim.trailing_zeros() as usize; // dim must be power of 2
        let mut state = Self::new(num_qubits);
        for (i, &v) in values.iter().enumerate() {
            state.amplitudes[i] = c64(v, 0.0);
        }
        state
    }

    /// Normalize the quantum state
    pub fn normalize(&mut self) {
        let mut norm_sq: f64 = 0.0;
        for amp in &self.amplitudes {
            norm_sq += amp.0 * amp.0 + amp.1 * amp.1;
        }
        
        let norm = norm_sq.sqrt();
        if norm > 1e-10 {
            for amp in &mut self.amplitudes {
                amp.0 /= norm;
                amp.1 /= norm;
            }
        }
    }

    /// Get measurement probabilities (Born rule)
    pub fn get_measurement_probabilities(&self) -> Vec<f64> {
        let mut probs = Vec::with_capacity(self.amplitudes.len());
        for amp in &self.amplitudes {
            probs.push(amp.0 * amp.0 + amp.1 * amp.1);
        }
        probs
    }

    /// Apply measurement (collapse to a basis state)
    pub fn measure(&mut self) -> usize {
        let probs = self.get_measurement_probabilities();
        
        // For now, return the index with highest probability
        let mut max_idx = 0;
        let mut max_prob = probs[0];
        for (i, &prob) in probs.iter().enumerate().skip(1) {
            if prob > max_prob {
                max_prob = prob;
                max_idx = i;
            }
        }
        
        // Collapse to the measured state
        for (i, amp) in self.amplitudes.iter_mut().enumerate() {
            if i == max_idx {
                *amp = c64(1.0, 0.0);
            } else {
                *amp = c64(0.0, 0.0);
            }
        }
        
        max_idx
    }
}

/// Quantum Gates for multi-qubit systems
pub enum QuantumGate {
    Hadamard { qubit: usize },
    PauliX { qubit: usize },
    PauliY { qubit: usize },
    PauliZ { qubit: usize },
    T { qubit: usize },
    S { qubit: usize },
    CNot { control: usize, target: usize },
    SWAP { qubit1: usize, qubit2: usize },
    Custom { matrix: Vec<Vec<c64>> },
}

impl QuantumGate {
    /// Apply gate to quantum state
    pub fn apply(&self, state: &mut QuantumState) {
        let num_qubits = state.num_qubits;
        let dim = state.amplitudes.len();
        
        match self {
            QuantumGate::Hadamard { qubit } => {
                if *qubit >= num_qubits {
                    panic!("Hadamard gate qubit index out of bounds");
                }
                self.apply_hadamard(state, *qubit);
            }
            QuantumGate::PauliX { qubit } => {
                if *qubit >= num_qubits {
                    panic!("PauliX gate qubit index out of bounds");
                }
                self.apply_pauli_x(state, *qubit);
            }
            QuantumGate::PauliY { qubit } => {
                if *qubit >= num_qubits {
                    panic!("PauliY gate qubit index out of bounds");
                }
                self.apply_pauli_y(state, *qubit);
            }
            QuantumGate::PauliZ { qubit } => {
                if *qubit >= num_qubits {
                    panic!("PauliZ gate qubit index out of bounds");
                }
                self.apply_pauli_z(state, *qubit);
            }
            QuantumGate::T { qubit } => {
                if *qubit >= num_qubits {
                    panic!("T gate qubit index out of bounds");
                }
                self.apply_t_gate(state, *qubit);
            }
            QuantumGate::S { qubit } => {
                if *qubit >= num_qubits {
                    panic!("S gate qubit index out of bounds");
                }
                self.apply_s_gate(state, *qubit);
            }
            QuantumGate::CNot { control, target } => {
                if *control >= num_qubits || *target >= num_qubits || *control == *target {
                    panic!("CNot gate qubit indices out of bounds or control == target");
                }
                self.apply_cnot(state, *control, *target);
            }
            QuantumGate::SWAP { qubit1, qubit2 } => {
                if *qubit1 >= num_qubits || *qubit2 >= num_qubits || *qubit1 == *qubit2 {
                    panic!("SWAP gate qubit indices out of bounds or qubit1 == qubit2");
                }
                self.apply_swap(state, *qubit1, *qubit2);
            }
            QuantumGate::Custom { matrix } => {
                if matrix.len() != dim || matrix[0].len() != dim {
                    panic!("Custom gate matrix dimension mismatch");
                }
                
                let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
                for i in 0..dim {
                    for j in 0..dim {
                        new_amplitudes[i].0 += matrix[i][j].0 * state.amplitudes[j].0 - matrix[i][j].1 * state.amplitudes[j].1;
                        new_amplitudes[i].1 += matrix[i][j].0 * state.amplitudes[j].1 + matrix[i][j].1 * state.amplitudes[j].0;
                    }
                }
                state.amplitudes = new_amplitudes;
            }
        }
        
        // Normalize after application
        state.normalize();
    }
    
    /// Apply Hadamard gate to specific qubit
    fn apply_hadamard(&self, state: &mut QuantumState, qubit: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        let h_factor = 1.0 / 2.0_f64.sqrt();
        
        for i in 0..dim {
            let qubit_val = (i >> qubit) & 1;
            let partner = i ^ (1 << qubit); // Flip the qubit bit
            
            if qubit_val == 0 {
                // H|0> = (|0> + |1>)/sqrt(2)
                new_amplitudes[i] = c64(
                    h_factor * state.amplitudes[i].0 + h_factor * state.amplitudes[partner].0,
                    h_factor * state.amplitudes[i].1 + h_factor * state.amplitudes[partner].1
                );
            } else {
                // H|1> = (|0> - |1>)/sqrt(2)
                // For the |1> state (qubit_val == 1), we need to apply the second row of H matrix: [1/sqrt(2), -1/sqrt(2)]
                // This means: new_amplitude[1] = h_factor * state.amplitudes[0] - h_factor * state.amplitudes[1]
                // But in the multi-qubit case, for state |i> where i's qubit bit is 1:
                // new_amplitudes[i] = h_factor * state.amplitudes[partner] - h_factor * state.amplitudes[i]
                new_amplitudes[i] = c64(
                    h_factor * state.amplitudes[partner].0 - h_factor * state.amplitudes[i].0,
                    h_factor * state.amplitudes[partner].1 - h_factor * state.amplitudes[i].1
                );
            }
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply Pauli X gate to specific qubit
    fn apply_pauli_x(&self, state: &mut QuantumState, qubit: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        for i in 0..dim {
            let partner = i ^ (1 << qubit); // Flip the qubit bit
            new_amplitudes[i] = state.amplitudes[partner];
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply Pauli Y gate to specific qubit
    fn apply_pauli_y(&self, state: &mut QuantumState, qubit: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        let i_comp = c64(0.0, 1.0);
        
        for i in 0..dim {
            let partner = i ^ (1 << qubit); // Flip the qubit bit
            let bit_val = (i >> qubit) & 1;
            
            if bit_val == 0 {
                // |0> -> -i|1>
                new_amplitudes[i] = -i_comp * state.amplitudes[partner];
            } else {
                // |1> -> i|0>
                new_amplitudes[i] = i_comp * state.amplitudes[partner];
            }
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply Pauli Z gate to specific qubit
    fn apply_pauli_z(&self, state: &mut QuantumState, qubit: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        for i in 0..dim {
            let bit_val = (i >> qubit) & 1;
            if bit_val == 0 {
                new_amplitudes[i] = state.amplitudes[i]; // |0> -> |0>
            } else {
                new_amplitudes[i] = c64(-state.amplitudes[i].0, -state.amplitudes[i].1); // |1> -> -|1>
            }
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply T gate to specific qubit
    fn apply_t_gate(&self, state: &mut QuantumState, qubit: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        // T = [[1, 0], [0, e^(i*π/4)]]
        let phase = PI / 4.0;
        let t11 = c64((phase).cos(), (phase).sin());
        
        for i in 0..dim {
            let bit_val = (i >> qubit) & 1;
            if bit_val == 0 {
                new_amplitudes[i] = state.amplitudes[i]; // |0> -> |0>
            } else {
                new_amplitudes[i] = t11 * state.amplitudes[i]; // |1> -> e^(i*π/4)|1>
            }
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply S gate to specific qubit
    fn apply_s_gate(&self, state: &mut QuantumState, qubit: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        // S = [[1, 0], [0, i]]
        let s11 = c64(0.0, 1.0);
        
        for i in 0..dim {
            let bit_val = (i >> qubit) & 1;
            if bit_val == 0 {
                new_amplitudes[i] = state.amplitudes[i]; // |0> -> |0>
            } else {
                new_amplitudes[i] = s11 * state.amplitudes[i]; // |1> -> i|1>
            }
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply CNOT gate
    fn apply_cnot(&self, state: &mut QuantumState, control: usize, target: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        for i in 0..dim {
            let control_bit = (i >> control) & 1;
            
            if control_bit == 0 {
                // Control is 0, don't flip target
                new_amplitudes[i] = state.amplitudes[i];
            } else {
                // Control is 1, flip target
                let flipped_target = i ^ (1 << target);
                new_amplitudes[flipped_target] = state.amplitudes[i];
            }
        }
        
        state.amplitudes = new_amplitudes;
    }
    
    /// Apply SWAP gate
    fn apply_swap(&self, state: &mut QuantumState, qubit1: usize, qubit2: usize) {
        let dim = state.amplitudes.len();
        let mut new_amplitudes = vec![c64(0.0, 0.0); dim];
        
        for i in 0..dim {
            let bit1 = (i >> qubit1) & 1;
            let bit2 = (i >> qubit2) & 1;
            
            // Swap the bits
            let new_bits = if bit1 == 0 && bit2 == 0 {
                i
            } else if bit1 == 1 && bit2 == 0 {
                i ^ (1 << qubit1) ^ (1 << qubit2)
            } else if bit1 == 0 && bit2 == 1 {
                i ^ (1 << qubit1) ^ (1 << qubit2)
            } else { // bit1 == 1 && bit2 == 1
                i
            };
            
            new_amplitudes[i] = state.amplitudes[new_bits];
        }
        
        state.amplitudes = new_amplitudes;
    }
}

/// Quantum Cognition Models
pub struct QuantumCognitionModel {
    pub state: QuantumState,
}

impl QuantumCognitionModel {
    /// Create a new quantum cognition model
    pub fn new(num_qubits: usize) -> Self {
        Self {
            state: QuantumState::new(num_qubits),
        }
    }
    
    /// Simulate quantum interference in decision making
    pub fn simulate_interference(&mut self, path1_probs: Vec<f64>, path2_probs: Vec<f64>) -> Vec<f64> {
        // Quantum interference: P = |amplitude1 + amplitude2|^2
        // where amplitude = sqrt(prob) * e^(i*phase)
        
        let mut interference_probs = Vec::with_capacity(path1_probs.len());
        
        for (p1, p2) in path1_probs.iter().zip(path2_probs.iter()) {
            // Simplified interference model
            let amplitude1 = (*p1).sqrt();
            let amplitude2 = (*p2).sqrt();
            
            // Constructive or destructive interference
            let interference_factor = 2.0 * amplitude1 * amplitude2 * 0.5; // 0.5 is average cosine phase
            
            let total_prob = p1 + p2 + interference_factor;
            interference_probs.push(total_prob.clamp(0.0, 1.0));
        }
        
        interference_probs
    }
    
    /// Simulate order effects in quantum cognition
    pub fn simulate_order_effects(&self, decision_a_prob: f64, decision_b_prob: f64, order: &str) -> f64 {
        // In quantum cognition, the order of questions affects answers
        // due to non-commutative measurements
        
        let mut base_prob = decision_a_prob;
        
        match order {
            "A_then_B" => {
                // Apply A then B
                base_prob = decision_a_prob * (1.0 - (1.0 - decision_b_prob) * 0.3); // Simplified model
            }
            "B_then_A" => {
                // Apply B then A
                base_prob = decision_b_prob * (1.0 - (1.0 - decision_a_prob) * 0.3); // Simplified model
            }
            _ => {}
        }
        
        base_prob.clamp(0.0, 1.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quantum_state_creation() {
        let state = QuantumState::new(2);
        assert_eq!(state.num_qubits, 2);
        assert_eq!(state.amplitudes.len(), 4); // 2^2 = 4
    }

    #[test]
    fn test_hadamard_gate_multi_qubit() {
        let mut state = QuantumState::new(1);
        state.amplitudes[0] = c64(1.0, 0.0); // |0>
        
        let hadamard = QuantumGate::Hadamard { qubit: 0 };
        hadamard.apply(&mut state);
        
        // After H|0>, should be (|0> + |1>)/sqrt(2)
        let expected = 1.0_f64 / 2.0_f64.sqrt();
        assert!((state.amplitudes[0].0 - expected).abs() < 1e-10);
        assert!((state.amplitudes[1].0 - expected).abs() < 1e-10);
    }

    #[test]
    fn test_cnot_gate() {
        let mut state = QuantumState::new(2);
        state.amplitudes[0] = c64(1.0_f64 / 2.0_f64.sqrt(), 0.0); // |00> amplitude
        state.amplitudes[1] = c64(1.0_f64 / 2.0_f64.sqrt(), 0.0); // |01> amplitude
        
        let cnot = QuantumGate::CNot { control: 0, target: 1 };
        cnot.apply(&mut state);
        
        // CNOT with control=0, target=1: 
        // |00> -> |00> (control=0, no flip)
        // |01> -> |11> (control=1, flip target)
        // So amplitude[0] should stay same, amplitude[1] should move to amplitude[3]
        assert!(state.amplitudes[0].0 > 0.0);
        assert!(state.amplitudes[3].0 > 0.0);
    }

    #[test]
    fn test_measurement_probabilities() {
        let mut state = QuantumState::new(1);
        state.amplitudes[0] = c64(1.0_f64 / 2.0_f64.sqrt(), 0.0);
        state.amplitudes[1] = c64(1.0_f64 / 2.0_f64.sqrt(), 0.0);
        
        let probs = state.get_measurement_probabilities();
        assert!((probs[0] - 0.5).abs() < 1e-10);
        assert!((probs[1] - 0.5).abs() < 1e-10);
    }

    #[test]
    fn test_quantum_cognition_interference() {
        let mut model = QuantumCognitionModel::new(1);
        let path1_probs = vec![0.5, 0.3];
        let path2_probs = vec![0.5, 0.3];
        
        let interference_probs = model.simulate_interference(path1_probs, path2_probs);
        
        assert_eq!(interference_probs.len(), 2);
        // With constructive interference, probabilities should be higher
        assert!(interference_probs[0] >= 0.5);
    }
}