class ApplicationController < ActionController::Base
  # Prevent CSRF attacks by raising an exception.
  # For APIs, you may want to use :null_session instead.
  protect_from_forgery with: :exception


  helper_method :current_user

  private
  #Using || 'pipes' helps us load the database once per page load as opposed to running back to it every method call
  def current_user
    @current_user ||= User.find(session[:user_id]) if session[:user_id]
  end


end