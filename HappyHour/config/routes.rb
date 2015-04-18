Rails.application.routes.draw do
  root 'pages#index'
  get 'about' => 'pages#about'
  get 'contact' => 'pages#contact'

  #Sign up Routes
  get 'signup' => 'users#new'
  post 'users' => 'users#create'

  #Log In / Log Out session Routes
  get 'login' => 'sessions#new'
  post 'login' => 'sessions#create'
  delete 'logout' => 'sessions#destroy'

  #User Routes
  get 'users/:id' => 'users#show', as: :user
  get "users/:id/edit" => "users#edit", as: :edit_user
  patch "users/:id" => "users#update"

  #Create new bars
  get 'bars/' => 'bars#index'
  get 'bars/new' => 'bars#new', as: :new_bar
  post 'bars/' => 'bars#create'

  #Edit Bars
  get 'bars/:id' => 'bars#show', as: :bar
  get "bars/:id/edit" => "bars#edit", as: :edit_bar
  patch "bars/:id" => "bars#update"
  delete "bars/:id" => "bars#destroy", as: :delete_bar


  #Offers Create
  get 'bars/:id/offers/' => 'offers#show'
  get 'bars/:id/offers/new' => 'offers#new', as: :bar_offers
  post 'bars/:id/offers/new' => 'offers#create'


  #Offers Edit
  get 'bars/:id/offers/:id/edit' => 'offers#edit', as: :edit_offer
  patch 'bars/:id/offers/:id' => 'offers#update', as: :offer
  delete 'bars/:id/offers/:id' => 'offers#destroy', as: :delete_offer





  #resources :bars






  # The priority is based upon order of creation: first created -> highest priority.
  # See how all your routes lay out with "rake routes".

  # You can have the root of your site routed with "root"
  # root 'welcome#index'

  # Example of regular route:
  #   get 'products/:id' => 'catalog#view'

  # Example of named route that can be invoked with purchase_url(id: product.id)
  #   get 'products/:id/purchase' => 'catalog#purchase', as: :purchase

  # Example resource route (maps HTTP verbs to controller actions automatically):
  #   resources :products

  # Example resource route with options:
  #   resources :products do
  #     member do
  #       get 'short'
  #       post 'toggle'
  #     end
  #
  #     collection do
  #       get 'sold'
  #     end
  #   end

  # Example resource route with sub-resources:
  #   resources :products do
  #     resources :comments, :sales
  #     resource :seller
  #   end

  # Example resource route with more complex sub-resources:
  #   resources :products do
  #     resources :comments
  #     resources :sales do
  #       get 'recent', on: :collection
  #     end
  #   end

  # Example resource route with concerns:
  #   concern :toggleable do
  #     post 'toggle'
  #   end
  #   resources :posts, concerns: :toggleable
  #   resources :photos, concerns: :toggleable

  # Example resource route within a namespace:
  #   namespace :admin do
  #     # Directs /admin/products/* to Admin::ProductsController
  #     # (app/controllers/admin/products_controller.rb)
  #     resources :products
  #   end
end
