-- =====================================================================
-- Base de datos del restaurante (SQLite)
-- Generada a partir de 5de5912f-tablas.xlsx
-- Llaves: PK = llave primaria, FK = llave foránea
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------- Limpieza (para poder volver a correr el script) ----------
DROP TABLE IF EXISTS detalle_venta;
DROP TABLE IF EXISTS venta;
DROP TABLE IF EXISTS empleado;
DROP TABLE IF EXISTS rol;
DROP TABLE IF EXISTS estado_dte;
DROP TABLE IF EXISTS forma_pago;
DROP TABLE IF EXISTS tipo_cliente;
DROP TABLE IF EXISTS platillo;
DROP TABLE IF EXISTS categoria_menu;
DROP VIEW IF EXISTS v_venta_total;

-- ---------- Catálogos ----------
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
    codigo     TEXT NOT NULL UNIQUE,             -- '01', '03', '11' (código tipoDte)
    documento  TEXT NOT NULL
);
CREATE TABLE forma_pago (
    id      INTEGER PRIMARY KEY,
    codigo  TEXT NOT NULL,                       -- Bitcoin y Lightning comparten el código 11
    nombre  TEXT NOT NULL UNIQUE
);
CREATE TABLE estado_dte (
    id      INTEGER PRIMARY KEY,
    paso    INTEGER NOT NULL UNIQUE,
    nombre  TEXT NOT NULL
);
CREATE TABLE rol (
    id      INTEGER PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE
            CHECK (nombre IN ('Asistente de caja', 'Administrador'))
);

-- ---------- Personal ----------
CREATE TABLE empleado (
    id              INTEGER PRIMARY KEY,
    rol_id          INTEGER NOT NULL,            -- FK -> rol.id
    nombre_usuario  TEXT UNIQUE,                 -- vacío en el Excel, por eso permite NULL
    password_hash   TEXT,                        -- hash de la contraseña (NULL = no puede iniciar sesión)
    FOREIGN KEY (rol_id) REFERENCES rol(id)
);

-- ---------- Transacciones ----------
CREATE TABLE venta (
    id               INTEGER PRIMARY KEY,        -- "ID Venta"
    fecha_hora       TEXT,                       -- ISO 8601: 'YYYY-MM-DD HH:MM:SS'
    cliente_nombre   TEXT,
    tipo_cliente_id  INTEGER NOT NULL,           -- FK -> tipo_cliente.id
    forma_pago_id    INTEGER NOT NULL,           -- FK -> forma_pago.id
    empleado_id      INTEGER,                    -- FK -> empleado.id ("Registrado por")
    estado_dte_id    INTEGER,                    -- FK -> estado_dte.id
    precio_btc_usd   REAL CHECK (precio_btc_usd IS NULL OR precio_btc_usd >= 0),
    FOREIGN KEY (tipo_cliente_id) REFERENCES tipo_cliente(id),
    FOREIGN KEY (forma_pago_id)   REFERENCES forma_pago(id),
    FOREIGN KEY (empleado_id)     REFERENCES empleado(id),
    FOREIGN KEY (estado_dte_id)   REFERENCES estado_dte(id)
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

-- ---------- Vista: campos calculados del Excel (Total venta, Total por línea) ----------
CREATE VIEW v_venta_total AS
SELECT v.id AS venta_id,
       v.fecha_hora,
       COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total_usd
FROM venta v
LEFT JOIN detalle_venta d ON d.venta_id = v.id
GROUP BY v.id;

-- =====================================================================
-- DATOS
-- =====================================================================
-- categoria_menu
INSERT INTO categoria_menu (id, nombre) VALUES (1, 'Desayunos');
INSERT INTO categoria_menu (id, nombre) VALUES (2, 'Aperitivos & Ensaladas');
INSERT INTO categoria_menu (id, nombre) VALUES (3, 'Hamburguesas & Sandwiches');
INSERT INTO categoria_menu (id, nombre) VALUES (4, 'Cuchillo & Tenedor');
INSERT INTO categoria_menu (id, nombre) VALUES (5, 'Fit Fare');
INSERT INTO categoria_menu (id, nombre) VALUES (6, 'Bebidas & Postres');

-- platillo (menú)
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (1, 1, 'Breakfast Chorizo Skillet', 'Papas rojas doradas cubiertas con queso derretido, chorizo, salsa de queso, jalapeños y plátano. Acompañadas de huevos estrellados, salsa de frijoles, crema y aguacate fresco.', 14);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (2, 1, 'Omelette con Loroco', 'Huevo, jamón dulce, hongos salteados y queso suizo derretido por dentro, bañado con nuestra cremosa salsa de loroco para darle ese toque único y tradicional. Acompañado con papas hashbrown y pan.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (3, 1, 'Desayuno Tipico con Loroco', 'Huevo revuelto con loroco, acompañado de frijoles fritos, plátano maduro, queso, crema y tortillas.', 10.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (4, 1, 'Chocolate Strawberry Waffle', 'Waffle caliente cubierto con fresas frescas y jugosas y crema de avellana, una combinación clásica de frutas y chocolate que nunca falla: fresca, dulce e irresistible.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (5, 1, 'Tres Leches Pancakes', 'Esponjosos buttermilk pancakes bañados en salsa de helado suave y caramelo salado. Decorados con canela en polvo, fresas frescas en rodajas y un toque de azúcar glass para un final dulce y cremoso.', 6.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (6, 1, 'Tres Leches Breakfast', 'Esponjosos buttermilk pancakes bañados en salsa de helado suave y caramelo salado. Decorados con canela en polvo, fresas frescas en rodajas y un toque de azúcar glass para un final dulce y cremoso. Se sirven con dos huevos*, papas hash brown, más dos tiras de tocino o dos salchichas.', 10.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (7, 1, 'Sweet caramel berries waffle', 'Un Belgian Waffle con deliciosas fresas y blueberries, caramelo y chocolate fudge. Cubierto con azúcar glas.', 4.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (8, 1, 'French Toast Slam', 'Tres rebanadas de tostada francesa. Se sirve con huevos*, tiras de tocino y salchichas.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (9, 1, 'French toast a la carta', '2 rebanadas de tostada francesa.', 3.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (10, 1, 'Desayuno Atomatado', 'Dos huevos revueltos con tomate, pimiento verde y cebolla con queso cheddar fundido, acompañados de frijoles (fritos o rancheros) plátano frito, aguacate, crema ácida, salsa ranchera y tu elección de tortillas o pan.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (11, 1, 'Waffles a la carta', 'Delicioso Belgian Waffle cubierto con azucar refinada.', 4);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (12, 1, 'The Grand Slam', 'Elige CUATRO opciones y hazlo a tu manera.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (13, 1, 'The Grand Slamwich', 'Dos huevos revueltos, salchicha, tocino crujiente, jamón, mayonesa y queso amercano en pan de papa importado y miel de especias, todo dorado a la plancha. Servido con tu elección de papas hash browns, papas fritas o frijoles (fritos o rancheros).', 11.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (14, 1, 'Lumberjack Slam', 'Dos panqueques, una rebanada de jamón a la plancha, dos tiras de tocino, dos salchichas, dos huevos, papas hash browns o frijoles (fritos o rancheros) y pan de tu elección.', 12.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (15, 1, 'Bacon Avocado Burrito', 'Tocino, aguacate, huevos revueltos, nuestro queso cheddar, pico de gallo y salsa chipotle; envuelto en una tortilla grande y asado a la plancha. Acompañado de papas hash browns o frijoles fritos o rancheros.', 9.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (16, 1, 'All American Slam', 'Tres huevos revueltos con queso cheddar, dos tiras de tocino, dos salchichas, servidos con papas hash browns o frijoles (fritos o rancheros) y pan de tu elección.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (17, 1, 'Ultimate Skillet', 'Espinaca fresca, salchicha, pimientos y cebollas asadas, champiñones, tomatitos y papas rojas sazonadas. Cubierto con una mezcla de queso y dos huevos cocinados a tu gusto en un sartén de hierro caliente.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (18, 1, 'Desayuno Tipico', 'Dos huevos al gusto, plátano maduro frito, mantequilla, queso crema, frijoles (fritos o rancheros), tortillas de maíz o de harina o pan de tu elección y salsa ranchera.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (19, 1, 'Huevos Divorciados', 'Dos huevos estrellados cocinados a tu gusto, bañados con salsa ranchera y salsa verde, acompañados de frijoles fritos con chips de tortillas de maíz, dos chorizos criollos, plátano maduro frito, queso crema y aguacate. Todo servido con tu elección de tortilla de maíz o de harina y una copita de mantequilla.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (20, 1, 'Moons Over My Hammy', 'Sándwich de dos huevos revueltos y jamón, con quesos suizo y americano, en pan sourdough a la plancha. Servido con papas hash browns, papas fritas o frijoles (fritos o rancheros).', 10.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (21, 1, 'Ham and Cheese Omelette', 'Omelette de tres huevos con trocitos de jamón y quesos suizo y americano derretidos.', 8.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (22, 1, 'Philly Cheesesteak Omelette', 'Omelette de tres huevos con prime rib a la parrilla, acompañado de pimientos, cebollas y champiñones salteados, con queso suizo derretido.', 11.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (23, 1, 'Cinnamon Roll Pancake Breakfast', 'Buttermilk pancakes cocinados con migas de canela, cubiertos con glaseado de queso crema. Se sirve con huevos*, papas hashbrown y tiras de tocino o salchichas.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (24, 1, 'Double Berry Banana Pancake Breakfast', 'Dos esponjosos buttermilk pancakes con jugosos arándanos azules cocinados por dentro y cubiertos con banano y fresas frescas. Servidos con dos huevos y papas hash browns, más tu elección de dos tiras de tocino o dos salchichas.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (25, 1, 'Choconana Pancake Breakfast', 'Chispas de chocolate dentro de dos buttermilk pancakes, cubiertos con banano más chispas de chocolate encima. Servidos con dos tiras tocino.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (26, 1, 'Belgian Waffle Slam', '1 Waffle servido con miel, dos huevos, dos tiras de tocino y dos salchichas.', 10.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (27, 2, 'Chilaquiles - Salsa Roja', 'Crujientes tortillas bañadas en salsa roja o verde caliente, acompañadas de pollo desmechado, salsa de frijoles, crema, tocino crujiente y aguacate fresco.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (28, 2, 'Chilaquiles - Salsa Verde', 'Crujientes tortillas bañadas en salsa roja o verde caliente, acompañadas de pollo desmechado, salsa de frijoles, crema, tocino crujiente y aguacate fresco.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (29, 2, 'Dip de Guacamole', 'Cremoso guacamole acompañado de crujientes tortilla chips y jalapeños. Perfecto para compartir.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (30, 2, 'Esquite', 'Cremoso maíz estilo esquite preparado con mayonesa, crema ácida, queso parmesano, Tajín y un toque de salsa Cholula. Acompañado de crujientes tortilla chips y limón fresco.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (31, 2, 'Nachos de Pollo', 'Nachos crujientes con queso fundido, pollo jugoso, pico de gallo y salsas, con topping fresco y presentación balanceada.', 9.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (32, 2, 'Sampler (Media Porcion)', 'Escoge dos y hazlo tuyo, servido con tu elección de salsas.', 9);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (33, 2, 'Zesty Nachos', 'Crujientes tortillas cubiertas de salsa de queso, carne molida premium condimentada, pico de gallo, salsa, guacamole y crema.', 9.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (34, 2, 'Quesadilla', 'Tortilla de harina rellena de pechuga de pollo sazonada y asada con trocitos de salchicha, pimientos y cebollas asadas al fuego, queso americano derretido y pico de gallo fresco. Servida con aderezo ranch.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (35, 2, 'Mozzarella Cheese Sticks', 'Palitos de queso servidos con salsa de tomate italiana.', 7.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (36, 2, 'Smothered Cheese Fries', 'Papas fritas cubiertas con salsa de queso, queso cheddar y tocino desmenuzado. Servidas con aderezo ranch.', 8.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (37, 2, 'Premium Chicken Tenders', 'Picositas tiras de pollo empanizadas con tu elección de salsa BBQ o salsa buffalo. Servidas con apio y salsa de tu elección.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (38, 2, 'Cranberry Apple Chicken Salad', 'Pechuga de pollo asada, nueces glaseadas y arándanos secos, sobre lechuga mixta. Servida con aderezo de vinagre balsámico o tu elección de aderezo y pan.', 9.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (39, 2, 'Avocado Caesar Salad', 'Elige entre una pechuga de pollo o un filete de salmón salvaje de Alaska, ambos perfectamente sazonados y asados, acompañados de aguacate fresco, tocino crujiente desmoronado y quesos italianos rallados por encima de lechuga romana fresca, mezclado con aderezo caesar y acompañada de pan.', 12.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (40, 3, 'Nacho Burger', 'Hamburguesa de res con queso americano, lechuga fresca, crujientes nachos, carne sazonada para nachos, jalapeños y pico de gallo. Acompañada de mayonesa y nuestro toque de mayonesa Spicy Sriracha. Servida con papas fritas.', 14);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (41, 3, 'Crispy Chicken Bacon Ranch Sandwich', 'Pan sourdough dorado a la plancha, rodajas de tomate, lechuga, queso derretido, tocino crujiente, Pechuga de pollo empanizada.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (42, 3, 'Classic Cheeseburger', 'Una porción de carne y tu elección de queso americano, suizo o cheddar. Servida con mayonesa, lechuga, tomate, pepinillos y cebolla roja.', 10.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (43, 3, 'Bacon Avocado Cheeseburger', 'Una hamburguesa cubierta de queso cheddar derretido, tocino crujiente y aguacate fresco. Servido en un pan brioche con mayonesa, lechuga, tomate, pepinillos y cebollas rojas.', 13.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (44, 3, 'Bacon Slamburger', 'Una hamburguesa 100% carne de res, con crujientes papas hash browns, un huevo cocinado a tu gusto, dos tiras de tocino y todo cubierto de salsa de queso.', 12.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (45, 3, 'America’s Dinner Double', 'Dos porciones de carne, queso americano, cebollas caramelizadas y salsa All-American en un pan brioche.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (46, 3, 'Spicy Sriracha Burger', 'Una hamburguesa 100% de res, sazonada en sriracha cubierta con queso cheddar, tocino, jalapeños, salsa cremosa de sriracha, lechuga, tomate, cebollas rojas y pepinillos.', 13.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (47, 3, 'Bourbon Bacon Burger', 'Una hamburguesa cubierta con queso cheddar, tocino, champiñones salteados, cebollas y pimientos asados al fuego, salsa bourbon, lechuga, tomate, cebollas rojas y pepinillos.', 13.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (48, 3, 'Double Cheeseburger', 'Dos porciones de carne premium y, tu elección de queso americano, suizo o cheddar. Servida con mayonesa, lechuga, tomate, pepinillos y cebolla roja.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (49, 3, 'Southwest Turkey Sandwich', 'Finas rebanadas de pechuga de pavo, aguacate fresco, queso suizo y salsa cremosa de pimienta entre dos rebanadas de pan sourdough a la plancha. Servido con papas a tu gusto.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (50, 3, 'The Super Bird', 'Rebanadas de pechuga de pavo con queso suizo derretido, tiras de tocino crujiente y tomate, en pan sourdough a la plancha.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (51, 3, 'Chicken Philly Melt', 'Pollo asado con champiñones, mezcla de pimientos y cebollas asadas, cubiertas con salsa de queso pepper jack y una mezcla de quesos rallados en pan hoagie a la plancha con una sabrosa mantequilla de ajo.', 12.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (52, 3, 'Club Sandwich', 'Finas rebanadas de jamón de pavo, tocino crujiente, lechuga, tomate y mayonesa en pan de 7 granos tostado.', 12);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (53, 4, 'Pollo con Loroco', 'Dos jugosas pechugas de pollo a la plancha, bañadas en una deliciosa y cremosa salsa de loroco. Acompañadas con tus dos complementos favoritos.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (54, 4, 'Pasta con Loroco', 'Una porción generosa de pasta cocida al dente, bañada en nuestra cremosa salsa de loroco, llena de sabor y tradición. Acompañada con pechuga de pollo a la plancha.', 13);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (55, 4, 'Chicken Alfredo Parmesan', 'Jugosa pasta con salsa alfredo, crujiente milanesa de pollo importada, queso parmesano y un toque de salsa marinara, acompaña de pan con ajo.', 11.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (56, 4, 'Camarones al ajillo', 'Camarones al ajillo servidos con tu elección de dos complementos. Servido con pan o tortilla.', 17.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (57, 4, 'Brooklyn Spaguetti & MeatBall', 'Una jugosa y fresca pasta de spaghetti con salsa Marinara, carne de res premium, champiñones, acompañada de queso parmesano importado y pan con ajo.', 14);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (58, 4, 'Premium Chicken Tenders', 'Cuatro picositas tiras de pollo empanizadas y doraditas servidas con una salsa para remojar, dos acompañantes de tu elección y pan.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (59, 4, 'Sweet and Tangy BBQ Chicken', 'Dos pechugas de pollo a la plancha y cubiertas con nuestra salsa BBQ. Servidas con nuestro puré de papas con queso cheddar, maíz y pan.', 13.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (60, 4, 'Cena Tipica', 'Elige entre un jugoso y suave churrasco de 5 onzas asado a la plancha, pechuga de pollo asada o una suculenta Hearty Sausage. Todo servido con plátano maduro frito, dos huevos, frijoles (fritos o rancheros), aguacate, queso crema, mantequilla, salsa ranchera y chimichurri.', 13);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (61, 4, 'California Steak', 'Jugoso y suave corte de res de 10 onzas asado a la plancha, servido con dos acompañamientos de tu elección y chimichurri.', 19.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (62, 4, 'Tilapia Ranchero', 'Un filete de pescado blanco a la plancha, cubierto de pico de gallo (picosito) y aguacate, Servido con arroz y un acompañamiento extra de tu elección.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (63, 4, 'Parrillada Personal', 'Típica parrillada al estilo nuestro con 5 onzas de churrasco, 5 onzas de pechuga de pollo a la plancha y chorizo criollo, todo cocinado a la perfección acompañado de nuestro nuevo casamiento caribeño, queso fresco, aguacate, crema ácida, pico de gallo, chimichurri y tortillas de maíz.', 19.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (64, 4, 'Bourbon Chicken Sizzlin Skillets', 'Pechugas de pollo sazonadas y a la parrilla, cubiertas con un glaseado de bourbon, coronadas con champiñones, cebollas y pimientos asados al fuego. Se sirve sobre brócoli y papas rojas sazonadas.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (65, 4, 'T-Bone Steak', 'Suave y jugoso steak de 13 oz, servido con 2 acompañamientos de tu eleccion.', 26);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (66, 5, 'Chicken Loaded Potato Skillet', 'Pechuga de pollo sazonada y asada con papas rojas sazonadas, tocino picadito y mezcla de vegetales cocidos. Servido en un sartén caliente, coronado con salsa de queso, queso cheddar rallado y una cucharada de crema ácida.', 12.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (67, 5, 'Fit Slam', 'Claras de huevo revueltas con espinaca y tomates cherry, más dos tiras de tocino de pavo, un english muffin y fruta de la temporada.', 8.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (68, 5, 'Turkey Omelette', 'Omelette de tres claras de huevo, jamon de pavo, pimienos, cebollas y champiñones salteados. Acompañado de queso fresc, aguacate, salsa verde y pan integral.', 11.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (69, 5, 'Chicken Avocado Sandwich', 'Una pechuga de pollo sazonada y asada, aguacate, pico de gallo, lechuga y crema ácida en pan integral de hamburguesa. Servido con vegetales frescos como tu opción de acompañamiento Fit Fare.', 11);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (70, 5, 'Fit Fare Veggie Skillet', 'Papas rojas sazonadas, cebollas y pimientos asados, champiñones y una mezcla de vegetales cocidos en un sartén de hierro caliente con dos claras de huevo revueltas con espinaca y tomates cherry. Servidos con salsa en un sartén de hierro caliente.', 10);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (71, 5, 'Smoky Gouda Chicken and Broccoli Skillet', 'Pollo sazonado y asado con cebollas caramelizadas, champiñones salteados y brócoli servidos sobre arroz de grano integral. Cubierto con quesos italianos y salsa de queso gouda.', 14.75);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (72, 6, 'Limonada Mandarina', 'Refrescante limonada con un toque dulce y cítrico de mandarina, servida bien fría y con un borde de tajín que le da el balance perfecto.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (73, 6, 'Limonada Pitahaya', 'Refrescante limonada con el sabor tropical y ligeramente dulce de la pitahaya, servida bien fría y coronada con una cereza.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (74, 6, 'Piña Colada Virgen', 'Cremosa y refrescante combinación de piña y crema de coco, perfectamente licuada con hielo y coronada con una cereza. Un clásico tropical sin alcohol', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (75, 6, 'Pecan Pie', 'Delicioso pie de nuez, cubierto con cremosa whipped cream y decorado con líneas de caramelo que hacen cada bocado dulce, crujiente y totalmente irresistible.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (76, 6, 'Tiramisu Frappe', 'Una deliciosa combinación de helado de vainilla, mezcla de cold brew y un toque de cacao en polvo Hershey, todo perfectamente licuado con hielo para lograr una textura cremosa y refrescante. Coronado con crema batida y espolvoreado con más cacao.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (77, 6, 'Caramel Iced Coffee', 'Nuestro cold brew se mezcla con caramelo para darle ese toque dulce y cremoso. Se sirve con hielo, un toque de leche, crema batida y tres líneas de caramelo por encima.', 6);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (78, 6, 'Wild Berries & Banana Smoothie', '¡Frutal, cremoso y 100% refrescante! Mezclamos banano, frutos rojos y leche para crear el smoothie perfecto.', 7);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (79, 6, 'Oreo Cheesecake', 'La combinación perfecta de dulzura y crujido de oreo y chocolate sobre un suave cheesecake y un toque de crema batida.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (80, 6, 'Mix berries cheesecake', 'La combinación perfecta de dulzura y crujido de oreo y chocolate sobre un suave cheesecake y un toque de crema batida.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (81, 6, 'Turtle Cheesecake', 'Irresistible combinacion de caramelo, chocolate y crujientes pecanas sobre un suave cheesecake y un toque de crema batida.', 7.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (82, 6, 'Refrescos y Agua', NULL, 2.5);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (83, 6, 'Specialty Drinks', 'No importa cuál es el café que más te gusta, tenemos uno para ti.', 4);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (84, 6, 'Pancake Puppies', 'Deliciosas pequeñas bolitas de masa de panqueque espolvoreadas con azúcar y canela, servidas con miel.', 3.25);
INSERT INTO platillo (id, categoria_id, nombre, descripcion, precio_desde) VALUES (85, 6, 'New York Style Cheesecake', 'New York Style Cheesecake', 7.25);

-- tipo_cliente
INSERT INTO tipo_cliente (id, codigo, documento) VALUES (1, '01', 'Factura');
INSERT INTO tipo_cliente (id, codigo, documento) VALUES (2, '03', 'Comprobante de Crédito Fiscal');
INSERT INTO tipo_cliente (id, codigo, documento) VALUES (3, '11', 'Factura de exportación');

-- forma_pago
INSERT INTO forma_pago (id, codigo, nombre) VALUES (1, '01', 'Efectivo');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (2, '02', 'Tarjeta débito');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (3, '03', 'Tarjeta crédito');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (4, '04', 'Cheque');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (5, '05', 'Transferencia');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (6, '06', 'Vales o cupones');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (7, '08', 'Dinero electrónico');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (8, '09', 'Monedero electrónico');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (9, '10', 'Certificado o tarjeta de regalo');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (10, '11', 'Bitcoin');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (11, '12', 'Otras criptomonedas');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (12, '99', 'Otros');
INSERT INTO forma_pago (id, codigo, nombre) VALUES (13, '11', 'Bitcoin Lightning');

-- estado_dte
INSERT INTO estado_dte (id, paso, nombre) VALUES (1, 1, 'Recibos emitidos');
INSERT INTO estado_dte (id, paso, nombre) VALUES (2, 2, 'DTE emitidos');
INSERT INTO estado_dte (id, paso, nombre) VALUES (3, 3, 'DTE firmado por comerciante');
INSERT INTO estado_dte (id, paso, nombre) VALUES (4, 4, 'DTE mandados a Hacienda');
INSERT INTO estado_dte (id, paso, nombre) VALUES (5, 5, 'DTE con sello de confirmación de Hacienda');

-- rol
INSERT INTO rol (id, nombre) VALUES (1, 'Asistente de caja');
INSERT INTO rol (id, nombre) VALUES (2, 'Administrador');


