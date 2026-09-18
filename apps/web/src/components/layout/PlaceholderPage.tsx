interface PlaceholderPageProps {
  titulo: string;
  descricao: string;
  fase: string;
}

export function PlaceholderPage({ titulo, descricao, fase }: PlaceholderPageProps) {
  return (
    <div className="placeholder-page">
      <h1>{titulo}</h1>
      <p>{descricao}</p>
      <p className="placeholder-fase">{fase}</p>
    </div>
  );
}
