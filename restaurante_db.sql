-- =====================================================================
-- Restaurant database (SQLite)
-- Generated from 5de5912f-tablas.xlsx
-- Keys: PK = primary key, FK = foreign key
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------- Cleanup (so the script can be re-run) ----------
DROP TABLE IF EXISTS detalle_venta;
DROP TABLE IF EXISTS venta;
DROP TABLE IF EXISTS empleado;
DROP TABLE IF EXISTS rol;
DROP TABLE IF EXISTS DTE_State;
DROP TABLE IF EXISTS forma_pago;
DROP TABLE IF EXISTS tipo_cliente;
DROP TABLE IF EXISTS platillo;
DROP TABLE IF EXISTS categoria_menu;
DROP VIEW IF EXISTS v_venta_total;

-- ---------- Catalogs ----------
CREATE TABLE categoria_menu (
    id      INTEGER PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE
);
CREATE TABLE platillo (
    id            INTEGER PRIMARY KEY,
    categoria_id  INTEGER NOT NULL,              -- FK -> categoria_menu.id
    nombre        TEXT NOT NULL,
    descripcion   TEXT,
    precio_desde  REAL NOT NULL CHECK (precio_desde >= 0),
    UNIQUE (categoria_id, nombre),
    FOREIGN KEY (categoria_id) REFERENCES categoria_menu(id)
);
CREATE TABLE tipo_cliente (
    id         INTEGER PRIMARY KEY,
    codigo     TEXT NOT NULL UNIQUE,             -- '01', '03', '11' (tipoDte code)
    documento  TEXT NOT NULL
);
CREATE TABLE forma_pago (
    id      INTEGER PRIMARY KEY,
    codigo  TEXT NOT NULL,                       -- Bitcoin and Lightning share code 11
    nombre  TEXT NOT NULL UNIQUE
);
CREATE TABLE DTE_State (
    id           INTEGER PRIMARY KEY,
    paso         INTEGER NOT NULL UNIQUE,
    nombre       TEXT NOT NULL,
    descripcion  TEXT
);
CREATE TABLE rol (
    id      INTEGER PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE
            CHECK (nombre IN ('Cashier Assistant', 'Administrator'))
);

-- ---------- Staff ----------
CREATE TABLE empleado (
    id              INTEGER PRIMARY KEY,
    rol_id          INTEGER NOT NULL,            -- FK -> rol.id
    nombre_usuario  TEXT UNIQUE,                 -- empty in the Excel, hence NULL is allowed
    password_hash   TEXT,                        -- password hash (NULL = cannot log in)
    FOREIGN KEY (rol_id) REFERENCES rol(id)
);

-- ---------- Transactions ----------
CREATE TABLE venta (
    id               INTEGER PRIMARY KEY,        -- "ID Venta"
    fecha_hora       TEXT,                       -- ISO 8601: 'YYYY-MM-DD HH:MM:SS'
    cliente_nombre   TEXT,
    tipo_cliente_id  INTEGER NOT NULL,           -- FK -> tipo_cliente.id
    forma_pago_id    INTEGER NOT NULL,           -- FK -> forma_pago.id
    empleado_id      INTEGER,                    -- FK -> empleado.id ("Registrado por")
    estado_dte_id    INTEGER,                    -- FK -> DTE_State.id
    precio_btc_usd   REAL CHECK (precio_btc_usd IS NULL OR precio_btc_usd >= 0),
    FOREIGN KEY (tipo_cliente_id) REFERENCES tipo_cliente(id),
    FOREIGN KEY (forma_pago_id)   REFERENCES forma_pago(id),
    FOREIGN KEY (empleado_id)     REFERENCES empleado(id),
    FOREIGN KEY (estado_dte_id)   REFERENCES DTE_State(id)
);
CREATE TABLE detalle_venta (
    id               INTEGER PRIMARY KEY,        -- "ID Detalle"
    venta_id         INTEGER NOT NULL,           -- FK -> venta.id
    platillo_id      INTEGER NOT NULL,           -- FK -> platillo.id
    cantidad         INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario  REAL NOT NULL CHECK (precio_unitario >= 0),  -- precio al momento de la venta
    FOREIGN KEY (venta_id)    REFERENCES venta(id) ON DELETE CASCADE,
    FOREIGN KEY (platillo_id) REFERENCES platillo(id)
);

-- ---------- View: calculated fields from the Excel (Sale total, Line total) ----------
CREATE VIEW v_venta_total AS
SELECT v.id AS venta_id,
       v.fecha_hora,
       COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total_usd
FROM venta v
LEFT JOIN detalle_venta d ON d.venta_id = v.id
GROUP BY v.id;

-- =====================================================================
-- DATA
-- =====================================================================
-- categoria_menu
INSERT INTO categoria_menu (id, nombre) VALUES (1, 'Breakfast');
INSERT INTO categoria_menu (id, nombre) VALUES (2, 'Appetizers & Salads');
INSERT INTO categoria_menu (id, nombre) VALUES (3, 'Burgers & Sandwiches');
INSERT INTO categoria_menu (id, nombre) VALUES (4, 'Knife & Fork');
INSERT INTO categoria_menu (id, nombre) VALUES (5, 'Fit Fare');
INSERT INTO categoria_menu (id, nombre) VALUES (6, 'Drinks & Desserts');

-- platillo (menu)
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (1, 1, 'Breakfast Chorizo Skillet', 'Golden red potatoes topped with melted cheese, chorizo, cheese sauce, jalapeños and plantain. Served with sunny-side-up eggs, bean sauce, sour cream and fresh avocado.', 14);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (2, 1, 'Loroco Omelette', 'Egg, sweet ham, sautéed mushrooms and melted Swiss cheese inside, topped with our creamy loroco sauce for that unique, traditional touch. Served with hashbrowns and bread.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (3, 1, 'Traditional Breakfast with Loroco', 'Scrambled eggs with loroco, served with fried beans, ripe plantain, cheese, sour cream and tortillas.', 10.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (4, 1, 'Chocolate Strawberry Waffle', 'Hot waffle topped with fresh, juicy strawberries and hazelnut cream, a classic fruit-and-chocolate combination that never fails: fresh, sweet and irresistible.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (5, 1, 'Tres Leches Pancakes', 'Fluffy buttermilk pancakes drizzled with soft ice cream sauce and salted caramel. Garnished with ground cinnamon, sliced fresh strawberries and a touch of powdered sugar for a sweet, creamy finish.', 6.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (6, 1, 'Tres Leches Breakfast', 'Fluffy buttermilk pancakes drizzled with soft ice cream sauce and salted caramel. Garnished with ground cinnamon, sliced fresh strawberries and a touch of powdered sugar for a sweet, creamy finish. Served with two eggs*, hash brown potatoes, plus two strips of bacon or two sausages.', 10.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (7, 1, 'Sweet caramel berries waffle', 'A Belgian waffle with delicious strawberries and blueberries, caramel and chocolate fudge. Topped with powdered sugar.', 4.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (8, 1, 'French Toast Slam', 'Three slices of French toast. Served with eggs*, bacon strips and sausages.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (9, 1, 'French toast a la carte', '2 slices of French toast.', 3.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (10, 1, 'Tomato Breakfast', 'Two scrambled eggs with tomato, green pepper and onion with melted cheddar cheese, served with beans (fried or ranchero style), fried plantain, avocado, sour cream, ranchero sauce and your choice of tortillas or bread.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (11, 1, 'Waffles a la carte', 'Delicious Belgian waffle topped with refined sugar.', 4);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (12, 1, 'The Grand Slam', 'Choose FOUR options and make it your way.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (13, 1, 'The Grand Slamwich', 'Two scrambled eggs, sausage, crispy bacon, ham, mayonnaise and American cheese on imported potato bread with spiced honey, all grilled to a golden brown. Served with your choice of hash browns, french fries or beans (fried or ranchero style).', 11.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (14, 1, 'Lumberjack Slam', 'Two pancakes, a slice of grilled ham, two strips of bacon, two sausages, two eggs, hash browns or beans (fried or ranchero style) and bread of your choice.', 12.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (15, 1, 'Bacon Avocado Burrito', 'Bacon, avocado, scrambled eggs, our cheddar cheese, pico de gallo and chipotle sauce; wrapped in a large tortilla and grilled. Served with hash browns or fried or ranchero beans.', 9.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (16, 1, 'All American Slam', 'Three scrambled eggs with cheddar cheese, two strips of bacon, two sausages, served with hash browns or beans (fried or ranchero style) and bread of your choice.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (17, 1, 'Ultimate Skillet', 'Fresh spinach, sausage, roasted peppers and onions, mushrooms, cherry tomatoes and seasoned red potatoes. Topped with a cheese blend and two eggs cooked to your liking in a hot iron skillet.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (18, 1, 'Traditional Breakfast', 'Two eggs any style, fried ripe plantain, butter, cream cheese, beans (fried or ranchero style), corn or flour tortillas or bread of your choice and ranchero sauce.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (19, 1, 'Divorced Eggs', 'Two sunny-side-up eggs cooked to your liking, covered with ranchero sauce and green sauce, served with fried beans with corn tortilla chips, two Creole chorizos, fried ripe plantain, cream cheese and avocado. All served with your choice of corn or flour tortilla and a small cup of butter.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (20, 1, 'Moons Over My Hammy', 'Sandwich of two scrambled eggs and ham, with Swiss and American cheeses, on grilled sourdough bread. Served with hash browns, french fries or beans (fried or ranchero style).', 10.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (21, 1, 'Ham and Cheese Omelette', 'Three-egg omelette with bits of ham and melted Swiss and American cheeses.', 8.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (22, 1, 'Philly Cheesesteak Omelette', 'Three-egg omelette with grilled prime rib, accompanied by sautéed peppers, onions and mushrooms, with melted Swiss cheese.', 11.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (23, 1, 'Cinnamon Roll Pancake Breakfast', 'Buttermilk pancakes cooked with cinnamon crumbs, topped with cream cheese icing. Served with eggs*, hashbrowns and strips of bacon or sausages.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (24, 1, 'Double Berry Banana Pancake Breakfast', 'Two fluffy buttermilk pancakes with juicy blueberries cooked inside and topped with fresh banana and strawberries. Served with two eggs and hash browns, plus your choice of two strips of bacon or two sausages.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (25, 1, 'Choconana Pancake Breakfast', 'Chocolate chips inside two buttermilk pancakes, topped with banana plus chocolate chips on top. Served with two strips of bacon.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (26, 1, 'Belgian Waffle Slam', '1 waffle served with honey, two eggs, two strips of bacon and two sausages.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (27, 2, 'Chilaquiles - Red Sauce', 'Crispy tortillas covered in hot red or green sauce, served with shredded chicken, bean sauce, sour cream, crispy bacon and fresh avocado.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (28, 2, 'Chilaquiles - Green Sauce', 'Crispy tortillas covered in hot red or green sauce, served with shredded chicken, bean sauce, sour cream, crispy bacon and fresh avocado.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (29, 2, 'Guacamole Dip', 'Creamy guacamole served with crispy tortilla chips and jalapeños. Perfect for sharing.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (30, 2, 'Esquite', 'Creamy esquite-style corn prepared with mayonnaise, sour cream, Parmesan cheese, Tajín and a touch of Cholula sauce. Served with crispy tortilla chips and fresh lime.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (31, 2, 'Chicken Nachos', 'Crispy nachos with melted cheese, juicy chicken, pico de gallo and sauces, with fresh toppings and a balanced presentation.', 9.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (32, 2, 'Sampler (Half Portion)', 'Choose two and make it yours, served with your choice of sauces.', 9);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (33, 2, 'Zesty Nachos', 'Crispy tortillas covered with cheese sauce, seasoned premium ground beef, pico de gallo, salsa, guacamole and sour cream.', 9.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (34, 2, 'Quesadilla', 'Flour tortilla filled with seasoned grilled chicken breast with bits of sausage, fire-roasted peppers and onions, melted American cheese and fresh pico de gallo. Served with ranch dressing.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (35, 2, 'Mozzarella Cheese Sticks', 'Cheese sticks served with Italian tomato sauce.', 7.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (36, 2, 'Smothered Cheese Fries', 'French fries covered with cheese sauce, cheddar cheese and crumbled bacon. Served with ranch dressing.', 8.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (37, 2, 'Premium Chicken Tenders', 'Spicy breaded chicken strips with your choice of BBQ or buffalo sauce. Served with celery and a sauce of your choice.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (38, 2, 'Cranberry Apple Chicken Salad', 'Grilled chicken breast, glazed walnuts and dried cranberries over mixed lettuce. Served with balsamic vinegar dressing or your choice of dressing, and bread.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (39, 2, 'Avocado Caesar Salad', 'Choose between a chicken breast or a wild Alaskan salmon fillet, both perfectly seasoned and grilled, served with fresh avocado, crumbled crispy bacon and grated Italian cheeses over fresh romaine lettuce tossed in Caesar dressing and served with bread.', 12.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (40, 3, 'Nacho Burger', 'Beef burger with American cheese, fresh lettuce, crispy nachos, seasoned nacho meat, jalapeños and pico de gallo. Served with mayonnaise and our Spicy Sriracha mayo touch. Served with french fries.', 14);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (41, 3, 'Crispy Chicken Bacon Ranch Sandwich', 'Grilled sourdough bread, tomato slices, lettuce, melted cheese, crispy bacon and breaded chicken breast.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (42, 3, 'Classic Cheeseburger', 'One beef patty and your choice of American, Swiss or cheddar cheese. Served with mayonnaise, lettuce, tomato, pickles and red onion.', 10.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (43, 3, 'Bacon Avocado Cheeseburger', 'A burger topped with melted cheddar cheese, crispy bacon and fresh avocado. Served on a brioche bun with mayonnaise, lettuce, tomato, pickles and red onions.', 13.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (44, 3, 'Bacon Slamburger', 'A 100% beef burger with crispy hash browns, an egg cooked to your liking, two strips of bacon and everything covered in cheese sauce.', 12.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (45, 3, 'America’s Dinner Double', 'Two beef patties, American cheese, caramelized onions and All-American sauce on a brioche bun.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (46, 3, 'Spicy Sriracha Burger', 'A 100% beef burger seasoned with sriracha, topped with cheddar cheese, bacon, jalapeños, creamy sriracha sauce, lettuce, tomato, red onions and pickles.', 13.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (47, 3, 'Bourbon Bacon Burger', 'A burger topped with cheddar cheese, bacon, sautéed mushrooms, fire-roasted onions and peppers, bourbon sauce, lettuce, tomato, red onions and pickles.', 13.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (48, 3, 'Double Cheeseburger', 'Two premium beef patties and your choice of American, Swiss or cheddar cheese. Served with mayonnaise, lettuce, tomato, pickles and red onion.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (49, 3, 'Southwest Turkey Sandwich', 'Thin slices of turkey breast, fresh avocado, Swiss cheese and creamy pepper sauce between two slices of grilled sourdough bread. Served with potatoes of your choice.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (50, 3, 'The Super Bird', 'Slices of turkey breast with melted Swiss cheese, crispy bacon strips and tomato, on grilled sourdough bread.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (51, 3, 'Chicken Philly Melt', 'Grilled chicken with mushrooms, a mix of roasted peppers and onions, covered with pepper jack cheese sauce and a blend of shredded cheeses on a grilled hoagie roll with tasty garlic butter.', 12.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (52, 3, 'Club Sandwich', 'Thin slices of turkey ham, crispy bacon, lettuce, tomato and mayonnaise on toasted 7-grain bread.', 12);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (53, 4, 'Chicken with Loroco', 'Two juicy grilled chicken breasts, covered in a delicious creamy loroco sauce. Served with your two favorite sides.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (54, 4, 'Pasta with Loroco', 'A generous portion of al dente pasta, covered in our creamy loroco sauce, full of flavor and tradition. Served with grilled chicken breast.', 13);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (55, 4, 'Chicken Alfredo Parmesan', 'Juicy pasta with Alfredo sauce, crispy imported breaded chicken cutlet, Parmesan cheese and a touch of marinara sauce, served with garlic bread.', 11.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (56, 4, 'Garlic Shrimp', 'Garlic shrimp served with your choice of two sides. Served with bread or tortilla.', 17.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (57, 4, 'Brooklyn Spaghetti & Meatball', 'A juicy, fresh spaghetti pasta with marinara sauce, premium beef, mushrooms, served with imported Parmesan cheese and garlic bread.', 14);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (58, 4, 'Premium Chicken Tenders', 'Four spicy, golden breaded chicken strips served with a dipping sauce, two sides of your choice and bread.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (59, 4, 'Sweet and Tangy BBQ Chicken', 'Two grilled chicken breasts covered with our BBQ sauce. Served with our cheddar cheese mashed potatoes, corn and bread.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (60, 4, 'Traditional Dinner', 'Choose between a juicy, tender 5-ounce grilled churrasco steak, grilled chicken breast or a succulent Hearty Sausage. All served with fried ripe plantain, two eggs, beans (fried or ranchero style), avocado, cream cheese, butter, ranchero sauce and chimichurri.', 13);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (61, 4, 'California Steak', 'Juicy, tender 10-ounce grilled cut of beef, served with two sides of your choice and chimichurri.', 19.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (62, 4, 'Ranchero Tilapia', 'A grilled white fish fillet, topped with pico de gallo (a little spicy) and avocado. Served with rice and an extra side of your choice.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (63, 4, 'Personal Grill Platter', 'Traditional grill platter our way with 5 ounces of churrasco, 5 ounces of grilled chicken breast and Creole chorizo, all cooked to perfection and served with our new Caribbean rice and beans, fresh cheese, avocado, sour cream, pico de gallo, chimichurri and corn tortillas.', 19.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (64, 4, 'Bourbon Chicken Sizzlin Skillets', 'Seasoned grilled chicken breasts, covered with a bourbon glaze, topped with mushrooms, and fire-roasted onions and peppers. Served over broccoli and seasoned red potatoes.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (65, 4, 'T-Bone Steak', 'Tender, juicy 13 oz steak, served with 2 sides of your choice.', 26);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (66, 5, 'Chicken Loaded Potato Skillet', 'Seasoned grilled chicken breast with seasoned red potatoes, chopped bacon and a mix of cooked vegetables. Served in a hot skillet, topped with cheese sauce, shredded cheddar cheese and a spoonful of sour cream.', 12.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (67, 5, 'Fit Slam', 'Scrambled egg whites with spinach and cherry tomatoes, plus two strips of turkey bacon, an English muffin and seasonal fruit.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (68, 5, 'Turkey Omelette', 'Three-egg-white omelette, turkey ham, sautéed peppers, onions and mushrooms. Served with fresh cheese, avocado, green sauce and whole wheat bread.', 11.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (69, 5, 'Chicken Avocado Sandwich', 'A seasoned grilled chicken breast, avocado, pico de gallo, lettuce and sour cream on a whole wheat burger bun. Served with fresh vegetables as your Fit Fare side option.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (70, 5, 'Fit Fare Veggie Skillet', 'Seasoned red potatoes, roasted onions and peppers, mushrooms and a mix of cooked vegetables in a hot iron skillet with two egg whites scrambled with spinach and cherry tomatoes. Served with sauce in a hot iron skillet.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (71, 5, 'Smoky Gouda Chicken and Broccoli Skillet', 'Seasoned grilled chicken with caramelized onions, sautéed mushrooms and broccoli served over brown rice. Topped with Italian cheeses and Gouda cheese sauce.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (72, 6, 'Tangerine Lemonade', 'Refreshing lemonade with a sweet, citrusy touch of tangerine, served ice cold with a Tajín rim that gives it the perfect balance.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (73, 6, 'Dragon Fruit Lemonade', 'Refreshing lemonade with the tropical, slightly sweet flavor of dragon fruit, served ice cold and topped with a cherry.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (74, 6, 'Virgin Piña Colada', 'Creamy, refreshing combination of pineapple and coconut cream, perfectly blended with ice and topped with a cherry. A non-alcoholic tropical classic.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (75, 6, 'Pecan Pie', 'Delicious pecan pie, topped with creamy whipped cream and decorated with caramel lines that make every bite sweet, crunchy and totally irresistible.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (76, 6, 'Tiramisu Frappe', 'A delicious combination of vanilla ice cream, cold brew blend and a touch of Hershey cocoa powder, all perfectly blended with ice for a creamy, refreshing texture. Topped with whipped cream and sprinkled with more cocoa.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (77, 6, 'Caramel Iced Coffee', 'Our cold brew is blended with caramel for that sweet, creamy touch. Served with ice, a splash of milk, whipped cream and three lines of caramel on top.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (78, 6, 'Wild Berries & Banana Smoothie', 'Fruity, creamy and 100% refreshing! We blend banana, red berries and milk to create the perfect smoothie.', 7);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (79, 6, 'Oreo Cheesecake', 'The perfect combination of sweetness and crunch of Oreo and chocolate over a soft cheesecake and a touch of whipped cream.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (80, 6, 'Mix berries cheesecake', 'The perfect combination of sweetness and crunch of Oreo and chocolate over a soft cheesecake and a touch of whipped cream.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (81, 6, 'Turtle Cheesecake', 'Irresistible combination of caramel, chocolate and crunchy pecans over a soft cheesecake and a touch of whipped cream.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (82, 6, 'Soft Drinks and Water', NULL, 2.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (83, 6, 'Specialty Drinks', 'No matter which coffee you like best, we have one for you.', 4);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (84, 6, 'Pancake Puppies', 'Delicious small balls of pancake batter sprinkled with sugar and cinnamon, served with honey.', 3.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (85, 6, 'New York Style Cheesecake', 'New York Style Cheesecake', 7.25);

-- tipo_cliente
INSERT INTO tipo_cliente (id, codigo, documento) VALUES (1, '01', 'Invoice');
INSERT INTO tipo_cliente (id, codigo, documento) VALUES (2, '03', 'Tax Credit Voucher');
INSERT INTO tipo_cliente (id, codigo, documento) VALUES (3, '11', 'Export Invoice');

-- forma_pago
INSERT INTO forma_pago (id, codigo, nombre) VALUES (1, '01', 'Cash');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (2, '02', 'Debit card');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (3, '03', 'Credit card');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (4, '04', 'Check');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (5, '05', 'Bank transfer');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (6, '06', 'Vouchers or coupons');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (7, '08', 'Electronic money');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (8, '09', 'Electronic wallet');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (9, '10', 'Gift certificate or card');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (10, '11', 'Bitcoin');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (11, '12', 'Other cryptocurrencies');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (12, '99', 'Other');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (13, '11', 'Bitcoin Lightning');

-- DTE_State
INSERT INTO DTE_State (id, paso, nombre, descripcion) VALUES (1, 1, 'Bill only', 'Receipts issued');
INSERT INTO DTE_State (id, paso, nombre, descripcion) VALUES (2, 2, 'DTE Done', 'DTEs issued');
INSERT INTO DTE_State (id, paso, nombre, descripcion) VALUES (3, 3, 'DTE Signed', 'DTE signed by merchant');
INSERT INTO DTE_State (id, paso, nombre, descripcion) VALUES (4, 4, 'DTE Sended', 'DTEs sent to Hacienda');
INSERT INTO DTE_State (id, paso, nombre, descripcion) VALUES (5, 5, 'DTE Approved', 'DTE with Hacienda confirmation seal');

-- rol
INSERT INTO rol (id, nombre) VALUES (1, 'Cashier Assistant');
INSERT INTO rol (id, nombre) VALUES (2, 'Administrator');


