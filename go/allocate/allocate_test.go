package allocate_test

import (
	"errors"
	"slices"
	"testing"

	"example.com/claudeguard/allocate"
)

func TestSplit(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name    string
		amount  int64
		weights []int64
		want    []int64
	}{
		{name: "even", amount: 100, weights: []int64{1, 1}, want: []int64{50, 50}},
		{name: "remainder to first", amount: 100, weights: []int64{1, 1, 1}, want: []int64{34, 33, 33}},
		{name: "proportional", amount: 10, weights: []int64{3, 1}, want: []int64{8, 2}},
		{name: "zero weight gets nothing", amount: 7, weights: []int64{0, 1, 1}, want: []int64{0, 4, 3}},
		{name: "zero amount", amount: 0, weights: []int64{2, 5}, want: []int64{0, 0}},
		{name: "single", amount: 9, weights: []int64{4}, want: []int64{9}},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			got, err := allocate.Split(tc.amount, tc.weights)
			if err != nil {
				t.Fatalf("Split(%d, %v) unexpected error: %v", tc.amount, tc.weights, err)
			}
			if !slices.Equal(got, tc.want) {
				t.Errorf("Split(%d, %v) = %v, want %v", tc.amount, tc.weights, got, tc.want)
			}
		})
	}
}

func TestSplitErrors(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name    string
		amount  int64
		weights []int64
		want    error
	}{
		{name: "negative amount", amount: -1, weights: []int64{1}, want: allocate.ErrNegativeAmount},
		{name: "no weights", amount: 1, weights: nil, want: allocate.ErrNoWeights},
		{name: "negative weight", amount: 1, weights: []int64{1, -1}, want: allocate.ErrNegativeWeight},
		{name: "all zero", amount: 1, weights: []int64{0, 0}, want: allocate.ErrZeroTotalWeight},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			got, err := allocate.Split(tc.amount, tc.weights)
			if !errors.Is(err, tc.want) {
				t.Fatalf("Split(%d, %v) error = %v, want %v", tc.amount, tc.weights, err, tc.want)
			}
			if got != nil {
				t.Errorf("Split(%d, %v) = %v, want nil on error", tc.amount, tc.weights, got)
			}
		})
	}
}
