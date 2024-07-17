---
hide:
  - toc
---

## Troubleshooting

Les capacités de Kubernetes et des modules déployés permettent de résoudre automatiquement des problèmes courants.

Monitorer Aristote Dispatcher permet toutefois de vérifier en permanence l'état du cluster, en particulier en cas de problème plus profond, non résolu automatiquement.

### Senders

- __Le nombre de senders fluctue__

    Ceci signifie que la connexion à la base de données ou à RabbitMQ ne s'effectue pas correctement. Les logs permettent d'obtenir plus d'informations.
    
    Dans le premier cas, elle est soit injoignable soit corrompue. Dans le second, le cluster RabbitMQ est peut-être détérioré.

### Consumers

- __Le nombre de consumers fluctue__

    Ceci signifie que la connexion à RabbitMQ ne s'effectue pas correctement. Les logs permettent d'obtenir plus d'informations.

    Le cluster RabbitMQ est peut-être détérioré. 

- __Un consumer redémarre en boucle de manière périodique__

    Ceci signifique que la connexion à vLLM ne s'effectue pas correctement. Les logs permettent d'obtenir plus d'informations.

    vLLM a probablement des difficultés à démarrer : carte graphique indisponible, modèle indisponible, ...

### RabbitMQ

- __Le cluster semble détérioré__

    Il faut identifier le ou les noeuds problématiques, et les redémarrer. Si votre monitoring le permet, inspecter l'état des queues permet de déterminer quels noeuds sont en retard (les moins remplis).

- __Le nombre de queues est trop petit__

    En fonctionnement normal, le nombre de queue doit être égal à la somme du nombre de senders et du nombre de modèles différents. S'il y a un problème, inspecter l'état des queues ou redémarrer les consumers (sans danger) permettra de résoudre le problème.

### vLLM

- __La latence est trop élevée__

    Cela signifie que les cartes graphiques reçoivent plus de demandes qu'elles ne peuvent traiter. Il faut alors augmenter le nombre de cartes graphiques sur votre cluster.