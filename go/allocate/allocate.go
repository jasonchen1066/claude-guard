package allocate

import "errors"

var (
	ErrNoWeights       = errors.New("allocate: no weights")
	ErrNegativeWeight  = errors.New("allocate: negative weight")
	ErrZeroTotalWeight = errors.New("allocate: weights sum to zero")
	ErrNegativeAmount  = errors.New("allocate: negative amount")
)

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
