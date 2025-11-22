package com.ttsudio.alphaback;

/**
 * Represents a trading order.
 * From: https://github.com/JustinTsangg/alphaback-model
 *
 * Note: This is a Java 8 compatible version of the record.
 */
public class Order {
    private final String stock;
    private final Float amount;
    private final Boolean isBuy;

    public Order(String stock, Float amount, Boolean isBuy) {
        this.stock = stock;
        this.amount = amount;
        this.isBuy = isBuy;
    }

    public String stock() {
        return stock;
    }

    public Float amount() {
        return amount;
    }

    public Boolean isBuy() {
        return isBuy;
    }
}
