from dotenv import load_dotenv
from flask import Flask,render_template,request,redirect,session,url_for,flash,jsonify
from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor
from google import genai
import markdown
import os
load_dotenv()
client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app=Flask(__name__)
app.secret_key=os.getenv("SECRET_KEY")

app.config['MYSQL_HOST']='mysql-b71ebab-harshitjhszxc1234-2fec.k.aivencloud.com'
app.config['MYSQL_USER']='avnadmin'
app.config['MYSQL_PASSWORD']=os.getenv("MYSQL_PASSWORD1")
app.config['MYSQL_DB']='defaultdb'
app.config['MYSQL_PORT']=11696
app.config['MYSQL_SSL_DISABLED']=False
mysql=MySQL(app)

@app.route('/',methods=['GET','POST'])
def home():
    search=request.form.get("search","")
    print(search)
    cursor=mysql.connection.cursor()
    cursor.execute("SELECT *FROM categories")
    categories=cursor.fetchall()
    if search:
        cursor.execute("SELECT *FROM products where name LIKE %s",('%' + search +'%',))
        
    else:
        cursor.execute("select *from products")    
    products=cursor.fetchall()
    cursor.close()
    return render_template('home.html',categories=categories,products=products)
    

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=request.form['username']
        email=request.form['email']
        password=request.form['password']
        cursor=mysql.connection.cursor()
        cursor.execute("INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",(username,email,password))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mysql.connection.cursor()
        cursor.execute("SELECT *FROM users where username=%s AND password=%s",(username,password))
        user=cursor.fetchone()
        cursor.close()
        if user:
            session['user']=username
            return redirect(url_for('home'))
        else:
            return "wrong username or password"
    return render_template('login.html')


@app.route('/products')
def products():

    search = request.args.get("search", "").strip()

    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    grouped = {}

    for cat in categories:

        if search:

            search_pattern = "%" + search + "%"
            start_pattern = search + "%"

            cursor.execute("""
                SELECT *,
                    CASE
                        WHEN LOWER(name) = LOWER(%s) THEN 100
                        WHEN LOWER(name) LIKE LOWER(%s) THEN 80
                        WHEN LOWER(name) LIKE LOWER(%s) THEN 60
                        WHEN LOWER(description) LIKE LOWER(%s) THEN 30
                        ELSE 0
                    END AS relevance

                FROM products

                WHERE category_id = %s

                AND (
                    LOWER(name) LIKE LOWER(%s)
                    OR LOWER(description) LIKE LOWER(%s)
                    OR LOWER(%s) LIKE LOWER(%s)
                )

                ORDER BY relevance DESC, name ASC

            """, (
                search,
                start_pattern,
                search_pattern,
                search_pattern,
                cat['id'],
                search_pattern,
                search_pattern,
                cat['name'],
                search_pattern
            ))

        else:

            cursor.execute(
                "SELECT * FROM products WHERE category_id = %s",
                (cat['id'],)
            )

        items = cursor.fetchall()

        if items:
            grouped[cat['name']] = items

    cursor.close()

    return render_template(
        'products.html',
        grouped=grouped,
        search=search
    )

@app.route('/product/<int:product_id>')
def product_details(product_id):
    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute(
        "SELECT * FROM products WHERE id = %s",
        (product_id,)
    )

    product = cursor.fetchone()
    cursor.close()

    if not product:
        return "Product not found", 404

    return render_template('products_details.html', product=product)
    
    
@app.route("/product_action/<int:product_id>", methods=["POST"])
def product_action(product_id):
    if "user" not in session:
        return redirect(url_for("login"))

    action = request.form.get("action")
    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id, name, price, image FROM products WHERE id=%s", (product_id,))
        product = cursor.fetchone()

        if not product:
            return "Product not found", 404

        if action == "cart":
            username = session["user"]
            
            # Optional: Check if item already exists in cart to update quantity instead of duplicating
            cursor.execute(
                "SELECT quantity FROM cart WHERE username=%s AND product_id=%s", 
                (username, product_id)
            )
            existing_item = cursor.fetchone()

            if existing_item:
                new_quantity = existing_item[0] + quantity
                cursor.execute(
                    "UPDATE cart SET quantity=%s WHERE username=%s AND product_id=%s",
                    (new_quantity, username, product_id)
                )
            else:
                cursor.execute("""
                    INSERT INTO cart (username, product_id, quantity, product_image, product_name, price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    username,
                    product[0],  # id
                    quantity,
                    product[3],  # image (adjust index based on your schema)
                    product[1],  # name
                    product[2]   # price
                ))

            mysql.connection.commit()
            return redirect(url_for("cart"))

        elif action == "buy":
            return redirect(url_for(
                "checkout",
                product_id=product_id,
                quantity=quantity
            ))
            
        return "Invalid action", 400

    finally:
        cursor.close()

        

@app.route('/checkout/<int:product_id>',methods=['GET','POST'])
def checkout(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    cursor=mysql.connection.cursor()
    cursor.execute("select * from products where id=%s",(product_id,))
    product=cursor.fetchone()
    if request.method=='POST':
        quantity = int(request.form["quantity"])
        # action = request.form["action"]
        name=request.form['name']
        phone=request.form['phone']
        address=request.form['address']
        # city=request.form['city']
        state=request.form['state']
        pincode=request.form['pincode']
        payment=request.form['payment']
        cursor.execute("INSERT INTO ORDERS(username,product_image,product_name,price,name,phone,address,state,pincode,payment_method,quantity) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(session['user'],product[5],product[2],product[3],name,phone,address,state,pincode,payment,quantity))
        cursor.execute("update products set stock = stock-%s where id=%s",(quantity,product_id))    
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('orders'))    
        # cursor.execute("Insert into orders ()")
    else:
        quantity=int(request.args.get("quantity",1))    

    return render_template("checkout.html",product=product,quantity=quantity)

@app.route('/cart')
def cart():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    cursor=mysql.connection.cursor()
    cursor.execute("""select cart.*,products.stock from cart join products on cart.product_id=products.id where cart.username=%s""",(session["user"],))
    items=cursor.fetchall()
    cursor.close()
    return render_template('cart.html',items=items)

@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    cursor=mysql.connection.cursor()
    cursor.execute("delete from cart where id=%s",(cart_id,))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('cart'))

@app.route('/increase_quantity/<int:cart_id>')
def increase_quantity(cart_id):
    if 'user' not in session:
        return jsonify({'error': 'login_required'}), 401

    cursor = mysql.connection.cursor()
    cursor.execute("select * from cart where id=%s", (cart_id,))
    cart = cursor.fetchone()
    cursor.execute("select stock from products where id=%s", (cart[2],))
    stock = cursor.fetchone()[0]

    new_qty = cart[6]
    if cart[6] < stock:
        new_qty = cart[6] +1
        cursor.execute("update cart set quantity=%s where id=%s", (new_qty, cart_id))
        mysql.connection.commit()

    cursor.close()
    return jsonify({'quantity': new_qty, 'max_reached': new_qty >= stock})


@app.route('/decrease_quantity/<int:cart_id>')
def decrease_quantity(cart_id):
    if 'user' not in session:
        return jsonify({'error': 'login_required'}), 401

    cursor = mysql.connection.cursor()
    cursor.execute("select * from cart where id=%s", (cart_id,))
    cart = cursor.fetchone()

    new_qty = cart[6]
    if cart[6] > 1:
        new_qty = cart[6] - 1
        cursor.execute("update cart set quantity=%s where id=%s", (new_qty, cart_id))
        mysql.connection.commit()

    cursor.close()
    return jsonify({'quantity': new_qty, 'min_reached': new_qty <= 1})   
    
# @app.route('/buy/<int:product_id>')
# def buy(product_id):
#     if 'user' not in session:
#         return redirect(url_for('login'))

#     cursor=mysql.connection.cursor()
#     cursor.execute("SELECT *FROM PRODUCTS WHERE id=%s",(product_id,))
#     product=cursor.fetchone()
#     return render_template("checkout.html",product=product)


@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    cursor=mysql.connection.cursor()
    cursor.execute("SELECT * FROM orders where username=%s ORDER BY id DESC",(session['user'],))
    orders=cursor.fetchall()
    cursor.close()
    return render_template('orders.html',orders=orders)

@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = 'Cancelled'
        WHERE id = %s AND username = %s
    """, (order_id, session['user']))

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('orders'))


@app.route('/logout')
def logout():
    session.pop('user')
    return redirect(url_for('login'))    
                       
@app.route('/chatbot',methods=['GET','POST'])
def chatbot():
    response=None
    user_message=None
    if request.method=='POST':
        user_message=request.form['message']
        try:
            result=client.models.generate_content(model='gemini-2.5-flash',contents=user_message)
            response=markdown.markdown(result.text)
        except Exception as e:
            response=f"Error:{str(e)}"    
    return render_template('chatbot.html',response=response,user_message=user_message)

@app.route('/admin/login',methods=['GET','POST'])
def admin():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mysql.connection.cursor()
        cursor.execute("select *from admins where username=%s and password=%s",(username,password))
        admin=cursor.fetchone()
        cursor.close()
        if admin:
            session['admin']=username
            return redirect(url_for('admin_dashboard'))
        else:
            return "wrong username or password"
    return render_template("admin_login.html") 

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():

    if 'admin' not in session:
        return redirect(url_for('admin'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    product_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE stock = 0")
    out_of_stock = cursor.fetchone()[0]
    cursor.execute("""
        SELECT * FROM orders
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_orders = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_dashboard.html",
        product_count=product_count,
        order_count=order_count,
        user_count=user_count,
        out_of_stock=out_of_stock,
        recent_orders=recent_orders
    )

@app.route('/admin/users')
def admin_users():
    if 'admin' not in session:
        return redirect(url_for('admin'))
    cursor=mysql.connection.cursor()
    cursor.execute("select *from users")
    users=cursor.fetchall()
    cursor.close()

    return render_template("admin_users.html",users=users)
    
@app.route('/admin/products')
def admin_products():
    if 'admin' not in session:
        return redirect(url_for('admin'))
    cursor=mysql.connection.cursor()
    cursor.execute("select *from products")
    products=cursor.fetchall()
    cursor.close()

    return render_template("admin_products.html",products=products)

@app.route('/admin/products/edit/<int:product_id>',methods=['POST','GET'])
def edit_product(product_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))
    cursor=mysql.connection.cursor()
    if request.method=="GET":
       cursor.execute("select *from products")
       products=cursor.fetchall()
       cursor.execute("select* from products where id=%s",(product_id,))
       product=cursor.fetchone()
       cursor.close()
       return render_template("admin_products.html",products=products,product=product)
    else:
        category_id=request.form['category_id']
        description=request.form['description']
        name=request.form['name']
        price=request.form['price']
        image=request.form['image']
        stock=request.form['stock']
        cursor.execute("update products set category_id=%s,description=%s, name=%s,price=%s,image=%s,stock=%s where id=%s",(category_id,description,name,price,image,stock,product_id))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('admin_products'))
 
@app.route('/admin/products/delete/<int:product_id>',methods=['GET','POST'])
def delete_products(product_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))
    cursor=mysql.connection.cursor()
    cursor.execute("delete from products where id=%s",(product_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('admin_products'))

@app.route('/admin/products/add',methods=['POST','GET'])
def add_products():
    if 'admin' not in session:
        return redirect(url_for('admin'))
    if request.method == 'POST':
       cursor=mysql.connection.cursor()
       category_id=request.form['category_id']
       name=request.form['name']
       price=request.form['price']
       description=request.form['description']
       image=request.form['image']
       stock=request.form['stock']
       cursor.execute("insert into products (category_id,name,price,description,image,stock) values (%s,%s,%s,%s,%s,%s)",(category_id,name,price,description,image,stock))
       mysql.connection.commit()
       cursor.close()
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
def admin_orders():
    if 'admin' not in session:
        return redirect(url_for('admin'))
    cursor=mysql.connection.cursor()
    cursor.execute("select *from orders ORDER BY id DESC")
    orders=cursor.fetchall()
    cursor.close()

    return render_template("admin_orders.html",orders=orders)

@app.route('/admin/orders/status/<int:order_id>',methods=['POST'])
def update_order_status(order_id):
    if 'admin' not in session:
        return redirect(url_for('admin'))
    if request.method == 'POST':
       status=request.form['status']
       cursor=mysql.connection.cursor()
       cursor.execute("update orders set status=%s where id=%s",(status,order_id))
       mysql.connection.commit()
       cursor.close()

    return redirect(url_for('admin_orders'))

@app.route('/admin/categories')
def admin_categories():
    if 'admin' not in session:
        return redirect(url_for('admin'))
    cursor=mysql.connection.cursor()
    cursor.execute("select *from categories")
    categories=cursor.fetchall()
    cursor.close()

    return render_template('admin_categories.html',categories=categories)


if __name__=='__main__':
    app.run(debug=True)




       

    
     


                
                    
            

