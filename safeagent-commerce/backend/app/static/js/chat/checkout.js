/**
 * chat/checkout.js — Checkout + Validator Gate Handler
 * ======================================================
 * Handles the checkout flow: calls /chat/checkout, processes
 * validator PASS/BLOCK response, then refreshes cart from DB.
 */

async function handleCheckout() {
    if (!activeCartId || cartItems.length === 0) return;
    checkoutState = "validating";
    updateValidatorBox();

    try {
        const data = await apiCheckout(activeCartId, sessionId);
        checkoutState = data.is_blocked ? "blocked" : "approved";
        updateValidatorBox(
            data.reply,
            data.is_blocked ? data.block_reason_code : "PASS",
            data.checkout_data
        );
        await fetchCartFromBackend();
    } catch (err) {
        checkoutState = "blocked";
        updateValidatorBox("Server error: " + err.message, "SERVER_ERROR");
    }
}
