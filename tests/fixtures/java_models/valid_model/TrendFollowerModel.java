package com.example;

import com.ttsudio.alphaback.*;
import java.util.*;

/**
 * Valid trading model - Trend Following Strategy
 * This model passes all verification checks
 */
public class TrendFollowerModel implements Model {

    @Override
    public List<Order> simulateStep(State state) {
        List<Order> orders = new ArrayList<>();

        Map<String, Float> prices = state.pricesMap();
        Map<String, Float> owned = state.ownedAssets();

        // Step 1: Sell all currently owned assets
        for (Map.Entry<String, Float> entry : owned.entrySet()) {
            String stock = entry.getKey();
            Float amount = entry.getValue();
            orders.add(new Order(stock, amount, false));  // Sell
        }

        // Step 2: Buy top 5 stocks (simple trend following)
        List<String> availableStocks = new ArrayList<>(prices.keySet());
        int buyCount = Math.min(5, availableStocks.size());

        for (int i = 0; i < buyCount; i++) {
            String stock = availableStocks.get(i);
            orders.add(new Order(stock, 2.0f, true));  // Buy 2 shares
        }

        return orders;
    }
}
