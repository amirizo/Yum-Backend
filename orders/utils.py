from .models import Cart, CartItem, Product

def get_cart_for_request(request):
    """
    Returns a tuple: (cart_object, cart_data_list, is_authenticated)
    - If authenticated: returns Cart instance from DB, cart_data_list is None
    - If guest: returns None for cart_object, cart_data_list from session
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart, None, True
    else:
        cart_data = request.session.get('cart', [])
        return None, cart_data, False


def add_item_to_cart(request, product_id, quantity=1, special_instructions=""):
    """
    Add or update a product in the cart for the given request.
    Works for both authenticated and anonymous users.
    """
    cart, cart_data, is_auth = get_cart_for_request(request)

    if is_auth:
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)
        if not created:
            cart_item.quantity += quantity
        cart_item.special_instructions = special_instructions
        cart_item.save()
        return cart_item
    else:
        for item in cart_data:
            if item['product_id'] == product_id:
                item['quantity'] += quantity
                item['special_instructions'] = special_instructions
                break
        else:
            cart_data.append({
                'product_id': product_id,
                'quantity': quantity,
                'special_instructions': special_instructions
            })
        request.session['cart'] = cart_data
        return cart_data


def update_cart_item(request, product_id, quantity, special_instructions=""):
    """
    Update quantity or instructions for a cart item.
    """
    cart, cart_data, is_auth = get_cart_for_request(request)

    if is_auth:
        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
            cart_item.quantity = quantity
            cart_item.special_instructions = special_instructions
            cart_item.save()
            return cart_item
        except CartItem.DoesNotExist:
            return None
    else:
        for item in cart_data:
            if item['product_id'] == product_id:
                item['quantity'] = quantity
                item['special_instructions'] = special_instructions
                break
        request.session['cart'] = cart_data
        return cart_data


def remove_cart_item(request, product_id):
    """
    Remove a product from the cart.
    """
    cart, cart_data, is_auth = get_cart_for_request(request)

    if is_auth:
        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
    else:
        cart_data = [item for item in cart_data if item['product_id'] != product_id]
        request.session['cart'] = cart_data


def clear_cart(request):
    """
    Clear all items from the cart.
    """
    cart, cart_data, is_auth = get_cart_for_request(request)

    if is_auth:
        cart.items.all().delete()
        cart.vendor = None
        cart.save()
    else:
        request.session['cart'] = []
