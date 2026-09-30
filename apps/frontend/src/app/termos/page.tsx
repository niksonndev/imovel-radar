import type { Metadata } from 'next';
import Link from 'next/link';

import { Footer } from '@/components/footer';
import { SITE_NAME } from '@/lib/site';

export const metadata: Metadata = {
  title: `Termos de Uso | ${SITE_NAME}`,
  description: 'Condições de uso do Imóvel Radar e limites do serviço.',
  alternates: { canonical: '/termos' },
};

export default function TermosPage() {
  return (
    <div className='flex flex-1 flex-col bg-surface text-white'>
      <main className='mx-auto w-full max-w-3xl flex-1 px-5 py-12 sm:py-16'>
        <Link
          href='/'
          className='font-mono text-xs uppercase text-primary-on-surface'
        >
          {SITE_NAME}
        </Link>
        <h1 className='mt-8 font-heading text-4xl'>Termos de Uso</h1>
        <p className='mt-3 text-sm text-white/60'>
          Última atualização: 29 de setembro de 2026
        </p>

        <div className='mt-10 space-y-8 leading-7 text-white/80'>
          <section>
            <h2 className='font-heading text-xl text-white'>O serviço</h2>
            <p className='mt-2'>
              O Imóvel Radar permite configurar alertas e acompanhar anúncios
              públicos do OLX em Maceió, Recife e Natal. O serviço avisa quando
              encontra correspondências segundo os filtros informados; não
              garante que um imóvel compatível será anunciado ou permanecerá
              disponível.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Anúncios e dados de mercado
            </h2>
            <p className='mt-2'>
              Anúncios, preços e disponibilidade são publicados por terceiros e
              podem mudar sem aviso. Médias e valores por metro quadrado são
              estatísticas de preços pedidos em anúncios ativos da coleta mais
              recente, não preços negociados, avaliação oficial ou recomendação
              de investimento. A negociação ocorre diretamente com o anunciante.
              O Imóvel Radar é um produto independente e não é afiliado nem
              endossado pela OLX.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Planos e pagamentos
            </h2>
            <p className='mt-2'>
              Os limites e recursos de cada plano são os apresentados no bot e
              no site no momento do uso. O acesso Pro depende de assinatura ou
              benefício de teste válido. Quando a cobrança recorrente por
              Telegram Stars estiver habilitada, sua renovação e cancelamento
              seguem a tela de assinatura do Telegram. O teste por e-mail é uma
              oferta separada, sujeita às regras mostradas no bot. O assistente
              não processa pagamento por Pix.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>Uso responsável</h2>
            <p className='mt-2'>
              Use o serviço apenas para fins lícitos, não tente acessar alertas
              de outras pessoas e não sobrecarregue os recursos do bot. A
              criação, remoção e acompanhamento estão sujeitos a validações e
              limites aplicados pelo serviço.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Limites e suporte
            </h2>
            <p className='mt-2'>
              O serviço não presta avaliação jurídica, financeira ou de
              investimento e não substitui a verificação do imóvel ou do
              anunciante. Para dúvidas de conta, cobrança, reclamações ou
              exercício de direitos, use o canal de contato no rodapé. O
              operador deve configurar um destino de atendimento humano antes de
              oferecer esse tipo de suporte. Consulte também a Política de
              Privacidade.
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
