class PagesController < ApplicationController

  def about
  end

  def contact
  end

  def index
    @users = User.all
    @bars = Bar.all
  end

  def new
    @user = User.new
  end

  def create
      @user = User.new(user_params)

      if @user.save
        redirect_to users_path
      else
        render :new
      end
  end


  def edit
    @user = User.find(params[:id])
  end

  def update
    @user = User.find(params[:id])

    if @user.update_attributes(params.require(:user).permit(:name, :password))
      redirect_to user_path(current_user)
    else
      render :edit
    end
  end #end update def


  private
  def user_params
    params.require(:user).permit(:name, :email, :password)
  end

end
