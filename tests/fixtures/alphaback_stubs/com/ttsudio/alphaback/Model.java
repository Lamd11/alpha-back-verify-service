package com.ttsudio.alphaback;

import java.util.List;

/**
 * Model interface that all trading models must implement.
 * From: https://github.com/JustinTsangg/alphaback-model
 */
public interface Model {
    /**
     * Execute one simulation step given the current market state.
     *
     * @param state The current market state (prices and owned assets)
     * @return List of orders to execute
     */
    List<Order> simulateStep(State state);
}
