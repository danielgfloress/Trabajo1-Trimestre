import express from "express";
import cors from "cors";

const app = express();
const PUERTO = 3000;

app.use(cors());
app.use(express.json());

app.get("/api/salud", (req, res) => {
  res.json({ estado: "ok", mensaje: "La API de D3 Kicks funciona" });
});

app.listen(PUERTO, () => {
  console.log(`API escuchando en el puerto ${PUERTO}`);
});
