// Package allocate splits an integer amount into parts proportional to weights.
package allocate

import "errors"

var (
	// ErrNoWeights is returned when no weights are given.
	ErrNoWeights = errors.New("allocate: no weights")
	// ErrNegativeWeight is returned when any weight is negative.
	ErrNegativeWeight = errors.New("allocate: negative weight")
	// ErrZeroTotalWeight is returned when all weights are zero.
	ErrZeroTotalWeight = errors.New("allocate: weights sum to zero")
	// ErrNegativeAmount is returned when the amount is negative.
	ErrNegativeAmount = errors.New("allocate: negative amount")
)

// Split divides amount into len(weights) parts proportional to weights.
// The parts always sum to amount; any remainder goes to the earliest parts.
func Split(amount int64, weights []int64) ([]int64, error) {
	if amount < 0 {
		return nil, ErrNegativeAmount
	}
	if len(weights) == 0 {
		return nil, ErrNoWeights
	}

	var total int64
	for _, w := range weights {
		if w < 0 {
			return nil, ErrNegativeWeight
		}
		total += w
	}
	if total == 0 {
		return nil, ErrZeroTotalWeight
	}

	parts := make([]int64, len(weights))
	var assigned int64
	for i, w := range weights {
		parts[i] = amount * w / total
		assigned += parts[i]
	}
	for i := 0; assigned < amount; i++ {
		if weights[i] > 0 {
			parts[i]++
			assigned++
		}
	}
	return parts, nil
}
