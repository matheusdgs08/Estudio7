# Regras de Negócio — Estúdio Se7e v3.0

> Documento completo disponível em `.docx` — este arquivo é o resumo markdown para referência rápida.

## 1. O Negócio
- Boutique fitness studio, máximo 9 alunos por turma
- 1 professor por aluno (rodízio dinâmico)
- Vendas 100% via WhatsApp + IA
- 2 números Z-API: comercial e recepção

## 2. Planos e Contratos
- Frequências: 1x a 5x por semana
- Modelo de créditos (não trava semanal)
- Contrato anual = pacote fechado de aulas

## 3. Tipos de Aluno
- **Fixo:** vagas geradas automaticamente para todo o contrato
- **Flexível:** `has_fixed_schedule = false`, agenda conforme disponibilidade

## 4. Cancelamento e Reposição
- +1h de antecedência → gera replacement_credit (sem prazo de 72h)
- <1h → aula perdida, sem crédito
- Falta → professor marca ao fechar aula
- Desmarcar reposição → perda definitiva

## 5. Hierarquia de Créditos
1. Reposições do contrato atual
2. Reposições transferidas do anterior
3. Créditos normais do plano
4. Crédito avulso

## 6. Lista de Espera
- Modelo sem reserva: notifica todos, primeiro a agendar garante
- Fixo só entra se tiver reposição disponível
- Remoção após 3 notificações sem ação

## 7. Sábado
- 7 vagas, não consome crédito
- Cancelamento sem penalidade

## 8. Rodízio de Professores
- 1:1 — cada aluno com 1 professor
- Critério: quem deu menos aulas no dia
- Salário fixo, sem comissão

## 9. Sistema de Treinos
- Sequência rotacional por aluno
- Falta não avança sequência
- Professor registra só alterações de carga
- Impressão automática 5 min antes da aula
- Aluno NÃO acessa treino pelo app

## 10. App do Aluno
- Agenda, créditos, frequência, avaliação física, financeiro próprio
- Push + WhatsApp
- SEM treino, SEM chat, cancelamento de contrato só pela recepção

## 11. Permissões
| Perfil | Acesso |
|--------|--------|
| Admin | Total |
| Coordinator (Vanessa) | Treinos, avaliação, aprovação de trocas |
| Recepção | Contratos, agenda, pausas |
| Professor | Horários escalados, registro de aula, ponto |
| Aluno | Agenda, créditos, frequência, avaliação, financeiro próprio |
