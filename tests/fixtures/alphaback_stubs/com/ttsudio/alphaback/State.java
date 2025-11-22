package com.ttsudio.alphaback;

import java.util.Map;

/**
 * Represents the current market state.
 * From: https://github.com/JustinTsangg/alphaback-model
 *
 * Note: This is a Java 8 compatible version of the record.
 */
public class State {
    private final Map<String, Float> pricesMap;
    private final Map<String, Float> ownedAssets;

    public State(Map<String, Float> pricesMap, Map<String, Float> ownedAssets) {
        this.pricesMap = pricesMap;
        this.ownedAssets = ownedAssets;
    }

    public Map<String, Float> pricesMap() {
        return pricesMap;
    }

    public Map<String, Float> ownedAssets() {
        return ownedAssets;
    }
}
