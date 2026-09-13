def cart_count(request):
    cart = request.session.get("cart", {})

    count = sum(
        int(quantity)
        for quantity in cart.values()
    )

    return {
        "cart_count": count
    }