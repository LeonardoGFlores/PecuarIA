import "dotenv/config";
import express from "express";
import cors from "cors";
import searchRouter from "./routes/search.js";

const app = express();
app.use(cors());
app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({ ok: true });
});

app.use("/api", searchRouter);

const port = Number(process.env.PORT ?? 3001);
app.listen(port, () => {
  console.log(`PecuarIA server listening on http://localhost:${port}`);
});
